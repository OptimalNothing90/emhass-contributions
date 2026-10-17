#!/usr/bin/env python3
"""Validate an EMHASS config (config.json / config.yaml) and optional runtime params.

Checks every key against EMHASS's own machine-readable schema files
(param_definitions.json, runtime_params.json, config_defaults.json,
associations.csv). Stdlib only; YAML configs need PyYAML, JSON needs nothing.
A copy of the v0.18.6 schema files ships next
to this script under ../schema/v0.18.6 and is used when --schema-dir is omitted.

Usage:
    validate_config.py <config.json|config.yaml> [--runtime runtimeparams.json]
                       [--schema-dir <dir>] [--quiet]

Output: one finding per line, "<SEVERITY>  <key>: <message>", sorted by severity
(ERROR, WARN, INFO). Exit code 0 = no errors, 1 = at least one ERROR,
2 = input could not be read.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

SEVERITY_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}

# Default schema bundle (upstream v0.18.6 copies). Override with --schema-dir.
BUNDLED_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema" / "v0.18.6"

# Upstream constants (src/emhass/utils.py @ v0.18.6). Kept verbatim so the
# validator agrees with build_params / treat_runtimeparams.
DEF_LOAD_ARRAY_PARAMS = (
    "start_timesteps_of_each_deferrable_load",
    "end_timesteps_of_each_deferrable_load",
    "set_deferrable_load_single_constant",
    "treat_deferrable_load_as_semi_cont",
    "set_deferrable_startup_penalty",
    "deferrable_load_max_cost",
    "set_deferrable_max_startups",
    "operating_hours_of_each_deferrable_load",
    "nominal_power_of_deferrable_loads",
    "def_minimum_on_time",
    "def_minimum_off_time",
    # Not padded by check_def_loads but still per-load:
    "minimum_power_of_deferrable_loads",
    "is_electric_load",
    "cost_forecast_per_deferrable_load",
)
DEF_LOAD_ARRAY_LEGACY_NAMES = {
    "def_start_timestep": "start_timesteps_of_each_deferrable_load",
    "def_end_timestep": "end_timesteps_of_each_deferrable_load",
    "set_def_constant": "set_deferrable_load_single_constant",
    "treat_def_as_semi_cont": "treat_deferrable_load_as_semi_cont",
    "def_start_penalty": "set_deferrable_startup_penalty",
    "def_total_hours": "operating_hours_of_each_deferrable_load",
    "P_deferrable_nom": "nominal_power_of_deferrable_loads",
}
BATT_ARRAY_PARAMS = (
    "battery_discharge_power_max",
    "battery_charge_power_max",
    "battery_discharge_efficiency",
    "battery_charge_efficiency",
    "battery_nominal_energy_capacity",
    "battery_minimum_state_of_charge",
    "battery_maximum_state_of_charge",
    "battery_target_state_of_charge",
    "battery_stress_cost",
    "battery_soc_deficit_threshold",
    "battery_soc_deficit_cost",
    "battery_soc_surplus_threshold",
    "battery_soc_surplus_cost",
    "weight_battery_charge",
    "weight_battery_discharge",
    "capacity_cost_per_kw",
    "capacity_charge_interval_timesteps",
    # Per-battery sensors (#610): one string at N=1, a list at N>1.
    "sensor_power_battery",
    "sensor_battery_state_of_charge",
)
SOC_FRACTION_PARAMS = (
    "battery_minimum_state_of_charge",
    "battery_maximum_state_of_charge",
    "battery_target_state_of_charge",
    "battery_soc_deficit_threshold",
    "battery_soc_surplus_threshold",
)
RUNTIME_SOC_FRACTION_PARAMS = ("soc_init", "soc_final", "soc_target")
RUNTIME_FORECAST_KEYS = (
    "pv_power_forecast",
    "pv_power_forecast_p10",
    "load_power_forecast",
    "load_cost_forecast",
    "prod_price_forecast",
    "outdoor_temperature_forecast",
)
# Runtime keys read by utils.treat_runtimeparams / command_line.py at v0.18.6 that
# are not listed in runtime_params.json (publish ids, ML actions, legacy names).
EXTRA_RUNTIME_KEYS = {
    "csv_file",
    "date_features",
    "delta_forecast",
    "delta_forecast_daily",
    "entity_save",
    "features",
    "freq",
    "heater_desired_temperatures",
    "heater_start_temperatures",
    "historic_days_to_retrieve",
    "days_to_retrieve",
    "ignore_pv_feedback_during_curtailment",
    "mlr_predict_device_class",
    "mlr_predict_entity_id",
    "mlr_predict_friendly_name",
    "mlr_predict_unit_of_measurement",
    "model_predict_device_class",
    "model_predict_entity_id",
    "model_predict_friendly_name",
    "model_predict_publish",
    "model_predict_unit_of_measurement",
    "model_type",
    "new_values",
    "num_lags",
    "perform_backtest",
    "publish_prefix",
    "regression_model",
    "sklearn_model",
    "solar_forecast_kwp",
    "solcast_api_key",
    "solcast_rooftop_id",
    "split_date_delta",
    "target",
    "time_zone",
    "timestamp",
    "var_model",
    "custom_batt_forecast_id",
    "custom_batt_soc_forecast_id",
    "custom_cost_fun_id",
    "custom_deferrable_forecast_id",
    "custom_deferrable_state_id",
    "custom_grid_forecast_id",
    "custom_heating_demand_id",
    "custom_hybrid_inverter_id",
    "custom_load_forecast_id",
    "custom_optim_status_id",
    "custom_predicted_temperature_id",
    "custom_pv_curtailment_id",
    "custom_pv_forecast_id",
    "custom_unit_load_cost_id",
    "custom_unit_prod_price_id",
}
# Keys that live in config_defaults.json / associations.csv only (headless loader).
EXTRA_CONFIG_KEYS = {"data_path"}

MPC_MIN_HORIZON = (
    5  # optimization.py: "Set the MPC prediction horizon to at least 5 ..."
)


@dataclass(frozen=True)
class Finding:
    severity: str
    key: str
    message: str

    def __str__(self) -> str:
        return f"{self.severity:<5} {self.key}: {self.message}"


# --------------------------------------------------------------------------- schemas


def _flatten_sections(doc: dict) -> dict:
    """param_definitions.json / runtime_params.json are {section: {key: def}}."""
    flat: dict = {}
    for section, params in doc.items():
        if not isinstance(params, dict):
            continue
        for key, definition in params.items():
            if isinstance(definition, dict):
                flat[key] = dict(definition, _section=section)
    return flat


def load_schemas(schema_dir: str | Path | None = None) -> dict:
    """Load the four schema files from schema_dir (default: bundled v0.18.6)."""
    base = Path(schema_dir) if schema_dir else BUNDLED_SCHEMA_DIR
    param_defs = _flatten_sections(
        json.loads((base / "param_definitions.json").read_text(encoding="utf-8"))
    )
    runtime_path = base / "runtime_params.json"
    runtime_defs = (
        _flatten_sections(json.loads(runtime_path.read_text(encoding="utf-8")))
        if runtime_path.exists()
        else {}
    )
    defaults_path = base / "config_defaults.json"
    config_defaults = (
        json.loads(defaults_path.read_text(encoding="utf-8"))
        if defaults_path.exists()
        else {}
    )
    legacy_names: dict[str, str] = {}
    assoc_params: set[str] = set()
    assoc_path = base / "associations.csv"
    if assoc_path.exists():
        with assoc_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                param = (row.get("parameter") or "").strip()
                legacy = (row.get("legacy_parameter_name") or "").strip()
                if param:
                    assoc_params.add(param)
                if legacy and param and legacy != param:
                    legacy_names[legacy] = param
    legacy_names.update(DEF_LOAD_ARRAY_LEGACY_NAMES)
    return {
        "param_defs": param_defs,
        "runtime_defs": runtime_defs,
        "config_defaults": config_defaults,
        "assoc_params": assoc_params,
        "legacy_names": legacy_names,
        "schema_dir": base,
    }


# ---------------------------------------------------------------------- config loading


LEGACY_SECTIONS = ("retrieve_hass_conf", "optim_conf", "plant_conf", "params_secrets")


def load_config(path: str | Path, legacy_names: dict[str, str] | None = None):
    """Read config.json or config.yaml. Returns (flat_config, notes).

    Legacy sectioned YAML (retrieve_hass_conf / optim_conf / plant_conf with the
    old parameter names) is flattened and renamed via associations.csv.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    notes: list[str] = []
    if path.suffix.lower() in (".yaml", ".yml"):
        # No fallback parser: a home-grown YAML subset reported broken files as
        # clean (Codex review 2026-10-17 finding 5). Refuse instead.
        try:
            import yaml  # type: ignore
        except ImportError:
            raise ValueError(
                "PyYAML is not installed; convert the config to JSON "
                "(e.g. save it from the EMHASS web UI) or 'pip install pyyaml'"
            ) from None
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML: {exc}") from exc
    else:
        doc = json.loads(text)
    if not isinstance(doc, dict):
        raise TypeError("config root must be a mapping")
    if doc and set(doc) <= set(LEGACY_SECTIONS):
        notes.append("legacy sectioned config detected; sections flattened")
        if legacy_names is None:
            legacy_names = load_schemas()["legacy_names"]
        flat: dict = {}
        for section in LEGACY_SECTIONS:
            for key, value in (doc.get(section) or {}).items():
                new_key = legacy_names.get(key, key)
                if new_key != key:
                    notes.append(f"legacy name {key} mapped to {new_key}")
                flat[new_key] = value
        doc = flat
    return doc, notes


# ------------------------------------------------------------------------- type checks

ATOMIC_CHECKS = {
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "select": lambda v: isinstance(v, str),
    "time": lambda v: isinstance(v, (str, dict)),
    "object": lambda v: isinstance(v, dict),
}


def _type_error(value, input_spec: str, path: str = "") -> str | None:
    """Return an error message when value does not match input_spec, else None."""
    if value is None:
        return None
    if input_spec.startswith("array."):
        inner = input_spec[len("array.") :]
        if not isinstance(value, list):
            if input_spec == "array.time" and isinstance(value, dict):
                return None  # load_peak_hour_periods is a mapping in config.json
            return f"{path or 'value'} must be a list ({input_spec}), got {type(value).__name__}"
        for i, element in enumerate(value):
            err = _type_error(element, inner, f"{path}[{i}]")
            if err:
                return err
        return None
    check = ATOMIC_CHECKS.get(input_spec)
    if check is None:
        return None  # unknown input kind: do not guess
    if not check(value):
        return f"{path or 'value'} must be {input_spec}, got {type(value).__name__}"
    return None


def _is_finite_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _suggest(key: str, candidates) -> str:
    match = difflib.get_close_matches(key, list(candidates), n=1, cutoff=0.75)
    return f" (did you mean {match[0]}?)" if match else ""


# ---------------------------------------------------------------------- config checks


def _check_keys(config: dict, schemas: dict, out: list[Finding]) -> None:
    known = (
        set(schemas["param_defs"])
        | set(schemas["config_defaults"])
        | schemas["assoc_params"]
        | EXTRA_CONFIG_KEYS
    )
    for key in config:
        if key in known:
            continue
        new_name = schemas["legacy_names"].get(key)
        if new_name:
            out.append(Finding("WARN", key, f"legacy parameter name; use {new_name}"))
        else:
            out.append(Finding("WARN", key, f"unknown key{_suggest(key, known)}"))


def _check_types(config: dict, schemas: dict, out: list[Finding]) -> None:
    for key, value in config.items():
        definition = schemas["param_defs"].get(key)
        if definition is None:
            continue
        if value is None:
            out.append(
                Finding("INFO", key, "null; EMHASS applies the parameter default")
            )
            continue
        spec = definition.get("input", "")
        if (
            key in BATT_ARRAY_PARAMS
            and spec.startswith("array.")
            and not isinstance(value, list)
        ):
            spec = spec[len("array.") :]  # scalar is broadcast to every battery (#610)
        err = _type_error(value, spec)
        if err:
            out.append(Finding("ERROR", key, err))
            continue
        options = definition.get("select_options")
        if spec == "select" and options and value not in options:
            out.append(
                Finding("ERROR", key, f"{value!r} not in select_options {options}")
            )


def _int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _check_deferrable_arrays(
    config: dict, out: list[Finding], prefix: str = ""
) -> None:
    n = _int_or_none(config.get("number_of_deferrable_loads"))
    if n is None:
        return
    for key in DEF_LOAD_ARRAY_PARAMS:
        value = config.get(key)
        if not isinstance(value, list):
            continue
        if len(value) < n:
            out.append(
                Finding(
                    "WARN",
                    prefix + key,
                    f"has {len(value)} entries but number_of_deferrable_loads={n}; "
                    "EMHASS pads with the parameter default",
                )
            )
        elif len(value) > n:
            out.append(
                Finding(
                    "WARN",
                    prefix + key,
                    f"has {len(value)} entries but number_of_deferrable_loads={n}; "
                    "extra entries are ignored",
                )
            )


def _check_battery_arrays(config: dict, out: list[Finding]) -> None:
    n = _int_or_none(config.get("number_of_batteries"))
    if n is None:
        n = 1
    for key in BATT_ARRAY_PARAMS:
        value = config.get(key)
        if isinstance(value, list) and len(value) != n:
            out.append(
                Finding(
                    "ERROR",
                    key,
                    f"has {len(value)} entries but number_of_batteries={n}; provide a scalar "
                    f"(broadcast to every battery) or a list of exactly {n} entries",
                )
            )


def _soc_values(value):
    """Yield (suffix, number) for a scalar or per-battery list."""
    if isinstance(value, list):
        for i, v in enumerate(value):
            if _is_finite_number(v):
                yield f"[{i}]", float(v)
    elif _is_finite_number(value):
        yield "", float(value)


def _check_soc(
    config: dict, out: list[Finding], params=SOC_FRACTION_PARAMS, prefix: str = ""
) -> None:
    for key in params:
        for suffix, v in _soc_values(config.get(key)):
            if v > 1.0 or v < 0.0:
                out.append(
                    Finding(
                        "ERROR",
                        prefix + key,
                        f"value{suffix}={v:g} is not a fraction in [0, 1] (percent? use {v / 100:g})",
                    )
                )
    if prefix:
        return
    mins = dict(_soc_values(config.get("battery_minimum_state_of_charge")))
    maxs = dict(_soc_values(config.get("battery_maximum_state_of_charge")))
    targets = dict(_soc_values(config.get("battery_target_state_of_charge")))
    for suffix, lo in mins.items():
        hi = maxs.get(suffix, maxs.get(""))
        if hi is not None and lo > hi:
            out.append(
                Finding(
                    "ERROR",
                    "battery_minimum_state_of_charge",
                    f"value{suffix}={lo:g} is above battery_maximum_state_of_charge={hi:g}",
                )
            )
    for suffix, tgt in targets.items():
        lo = mins.get(suffix, mins.get(""))
        hi = maxs.get(suffix, maxs.get(""))
        if (lo is not None and tgt < lo) or (hi is not None and tgt > hi):
            out.append(
                Finding(
                    "WARN",
                    "battery_target_state_of_charge",
                    f"value{suffix}={tgt:g} lies outside [min, max] SOC "
                    f"[{lo if lo is not None else '?'}, {hi if hi is not None else '?'}]; "
                    "EMHASS clamps it",
                )
            )


def _check_hybrid_inverter(config: dict, out: list[Finding]) -> None:
    if config.get("inverter_is_hybrid") is not True:
        return
    for key in ("inverter_ac_output_max", "inverter_ac_input_max"):
        value = config.get(key)
        if _is_finite_number(value) and value <= 0:
            out.append(
                Finding(
                    "ERROR",
                    key,
                    f"is {value:g} with inverter_is_hybrid=true: the AC<->DC transfer limit "
                    "becomes 0 W, so PV, battery and grid are pinned to zero and the "
                    "optimization turns infeasible (upstream issue #875). Set the real "
                    "inverter rating in W.",
                )
            )


def _check_deferrable_timing(config: dict, out: list[Finding]) -> None:
    step_min = _int_or_none(config.get("optimization_time_step"))
    if step_min is not None and step_min > 0 and 60 % step_min != 0:
        out.append(
            Finding(
                "WARN",
                "optimization_time_step",
                f"{step_min} min does not divide an hour; use 5, 10, 15, 20, 30 or 60",
            )
        )
    dt_h = (step_min / 60.0) if step_min else None
    days = _int_or_none(config.get("delta_forecast_daily")) or 1
    horizon_h = 24.0 * days
    hours = config.get("operating_hours_of_each_deferrable_load")
    semi = config.get("treat_deferrable_load_as_semi_cont")
    if isinstance(hours, list):
        for k, h in enumerate(hours):
            if not _is_finite_number(h) or h <= 0:
                continue
            if h > horizon_h:
                out.append(
                    Finding(
                        "WARN",
                        "operating_hours_of_each_deferrable_load",
                        f"[{k}]={h:g} h exceeds the {horizon_h:g} h horizon "
                        f"(delta_forecast_daily={days}); the load can never complete",
                    )
                )
            is_semi = isinstance(semi, list) and k < len(semi) and semi[k] is True
            if dt_h and is_semi:
                steps = h / dt_h
                if abs(steps - round(steps)) > 1e-9:
                    out.append(
                        Finding(
                            "WARN",
                            "operating_hours_of_each_deferrable_load",
                            f"[{k}]={h:g} h is not a whole number of {step_min}-min timesteps "
                            f"for a semi-continuous load; EMHASS rounds up to "
                            f"{math.ceil(steps) * dt_h:g} h ({math.ceil(steps)} steps)",
                        )
                    )
    starts = config.get("start_timesteps_of_each_deferrable_load")
    ends = config.get("end_timesteps_of_each_deferrable_load")
    if isinstance(starts, list) and isinstance(ends, list):
        for k, (s, e) in enumerate(zip(starts, ends)):
            if _is_finite_number(s) and _is_finite_number(e) and e != 0 and e < s:
                out.append(
                    Finding(
                        "ERROR",
                        "end_timesteps_of_each_deferrable_load",
                        f"[{k}]={e:g} is before start_timesteps_of_each_deferrable_load[{k}]={s:g}",
                    )
                )
    if dt_h and isinstance(ends, list):
        max_steps = int(horizon_h / dt_h)
        for k, e in enumerate(ends):
            if _is_finite_number(e) and e > max_steps:
                out.append(
                    Finding(
                        "WARN",
                        "end_timesteps_of_each_deferrable_load",
                        f"[{k}]={e:g} is beyond the {max_steps}-step horizon; EMHASS clamps it",
                    )
                )


# --------------------------------------------------------------------- runtime checks


def _check_runtime(
    runtime: dict, config: dict, schemas: dict, out: list[Finding]
) -> None:
    prefix = "runtime."
    known = (
        set(schemas["runtime_defs"])
        | set(schemas["param_defs"])
        | set(schemas["config_defaults"])
        | schemas["assoc_params"]
        | set(RUNTIME_FORECAST_KEYS)
        | EXTRA_RUNTIME_KEYS
        | set(schemas["legacy_names"])
    )
    for key, value in runtime.items():
        if key not in known:
            out.append(
                Finding(
                    "WARN", prefix + key, f"unknown runtime key{_suggest(key, known)}"
                )
            )
            continue
        new_name = schemas["legacy_names"].get(key)
        if (
            new_name
            and key not in schemas["param_defs"]
            and key not in schemas["runtime_defs"]
        ):
            out.append(
                Finding("INFO", prefix + key, f"legacy runtime name; prefer {new_name}")
            )
        if key in RUNTIME_FORECAST_KEYS:
            _check_forecast_values(prefix + key, value, out)
            continue
        definition = schemas["runtime_defs"].get(key) or schemas["param_defs"].get(key)
        if definition is None or value is None:
            continue
        spec = definition.get("input", "")
        if (
            key in BATT_ARRAY_PARAMS
            and spec.startswith("array.")
            and not isinstance(value, list)
        ):
            spec = spec[len("array.") :]
        err = _type_error(value, spec)
        if err:
            out.append(Finding("ERROR", prefix + key, err))
            continue
        options = definition.get("select_options")
        if spec == "select" and options and value not in options:
            out.append(
                Finding(
                    "ERROR", prefix + key, f"{value!r} not in select_options {options}"
                )
            )
    _check_soc(runtime, out, params=RUNTIME_SOC_FRACTION_PARAMS, prefix=prefix)
    _check_soc(runtime, out, params=SOC_FRACTION_PARAMS, prefix=prefix)
    horizon = runtime.get("prediction_horizon")
    if _is_finite_number(horizon) and horizon < MPC_MIN_HORIZON:
        out.append(
            Finding(
                "ERROR",
                prefix + "prediction_horizon",
                f"{horizon:g} is below {MPC_MIN_HORIZON}; naive-mpc-optim refuses to run "
                "(optimization.py: prediction horizon must be at least 5 timesteps)",
            )
        )
    # Length-check only the per-load arrays the payload itself overrides.
    n_loads = runtime.get(
        "number_of_deferrable_loads", config.get("number_of_deferrable_loads")
    )
    overrides = {k: v for k, v in runtime.items() if k in DEF_LOAD_ARRAY_PARAMS}
    if overrides:
        _check_deferrable_arrays(
            dict(overrides, number_of_deferrable_loads=n_loads), out, prefix=prefix
        )


def _check_forecast_values(key: str, value, out: list[Finding]) -> None:
    if isinstance(value, dict):
        values = list(value.values())
    elif isinstance(value, list):
        values = value
    elif isinstance(value, str):
        out.append(
            Finding(
                "INFO", key, "forecast passed as a string; EMHASS parses it as a list"
            )
        )
        return
    else:
        out.append(
            Finding(
                "ERROR",
                key,
                f"must be a list or {{timestamp: value}} mapping, got {type(value).__name__}",
            )
        )
        return
    if not values:
        out.append(Finding("ERROR", key, "forecast is empty"))
        return
    for i, v in enumerate(values):
        if not _is_finite_number(v):
            out.append(
                Finding(
                    "ERROR",
                    key,
                    f"[{i}]={v!r} is not a finite number; EMHASS rejects the whole forecast "
                    "and the cycle fails before the solver",
                )
            )
            return


# -------------------------------------------------------------------------- driver


def validate(config: dict, schemas: dict, runtime: dict | None = None) -> list[Finding]:
    out: list[Finding] = []
    _check_keys(config, schemas, out)
    _check_types(config, schemas, out)
    _check_deferrable_arrays(config, out)
    _check_battery_arrays(config, out)
    _check_soc(config, out)
    _check_hybrid_inverter(config, out)
    _check_deferrable_timing(config, out)
    if runtime:
        _check_runtime(runtime, config, schemas, out)
    out.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.key))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("config", help="config.json or config.yaml")
    parser.add_argument(
        "--runtime", help="runtimeparams JSON file (the POST /action payload)"
    )
    parser.add_argument(
        "--schema-dir", help="directory holding param_definitions.json etc."
    )
    parser.add_argument("--quiet", action="store_true", help="hide INFO findings")
    args = parser.parse_args(argv)

    try:
        schemas = load_schemas(args.schema_dir)
    except (OSError, ValueError) as exc:
        print(f"ERROR schema: cannot read schema files: {exc}")
        return 2
    try:
        config, notes = load_config(args.config, schemas["legacy_names"])
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR config: cannot read {args.config}: {exc}")
        return 2
    runtime = None
    if args.runtime:
        try:
            runtime = json.loads(Path(args.runtime).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"ERROR runtime: cannot read {args.runtime}: {exc}")
            return 2
        if not isinstance(runtime, dict):
            print("ERROR runtime: payload must be a JSON object")
            return 2

    print(f"schema: {schemas['schema_dir']}")
    for note in notes:
        print(f"note: {note}")
    findings = validate(config, schemas, runtime=runtime)
    shown = [f for f in findings if not (args.quiet and f.severity == "INFO")]
    for finding in shown:
        print(finding)
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}
    verdict = "FAIL" if counts["ERROR"] else "OK"
    print(
        f"{verdict}: {counts['ERROR']} error(s), {counts['WARN']} warning(s), {counts['INFO']} info"
    )
    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
