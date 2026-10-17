"""Tests for skills/emhass-config-validate/scripts/validate_config.py.

Fixtures derive from upstream config_defaults.json (v0.18.6) plus deliberately
broken variants. Every finding is a (severity, key, message) tuple; the CLI
prints one finding per line and exits non-zero when an ERROR is present.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "emhass-config-validate"
    / "scripts"
    / "validate_config.py"
)


def _findings(mod, config: dict, runtime: dict | None = None, schema_dir=None):
    schemas = mod.load_schemas(schema_dir)
    return mod.validate(config, schemas, runtime=runtime)


def _keys(findings, severity=None):
    return {f.key for f in findings if severity is None or f.severity == severity}


def _by_key(findings, key):
    return [f for f in findings if f.key == key]


# ---------------------------------------------------------------- baseline


def test_defaults_produce_no_errors(validate_config_mod, config_defaults, schema_dir):
    findings = _findings(validate_config_mod, config_defaults, schema_dir=schema_dir)
    errors = [f for f in findings if f.severity == "ERROR"]
    assert errors == [], [str(f) for f in errors]


def test_defaults_with_pv_and_battery_enabled_produce_no_errors(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["set_use_pv"] = True
    cfg["set_use_battery"] = True
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert [f for f in findings if f.severity == "ERROR"] == []


# ------------------------------------------------------------ unknown keys


def test_unknown_key_is_reported(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["numbr_of_deferrable_loads"] = 2
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hits = _by_key(findings, "numbr_of_deferrable_loads")
    assert hits and hits[0].severity == "WARN"
    assert "unknown" in hits[0].message.lower()


def test_unknown_key_suggests_close_match(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["numbr_of_deferrable_loads"] = 2
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert (
        "number_of_deferrable_loads"
        in _by_key(findings, "numbr_of_deferrable_loads")[0].message
    )


def test_legacy_parameter_name_is_flagged_with_new_name(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["freq"] = 30  # legacy name of optimization_time_step (associations.csv)
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "freq")[0]
    assert hit.severity == "WARN"
    assert "optimization_time_step" in hit.message


def test_keys_known_only_to_config_defaults_are_not_unknown(
    validate_config_mod, config_defaults, schema_dir
):
    # data_path, model_type, ... exist in config_defaults.json but not in param_definitions.json
    findings = _findings(validate_config_mod, config_defaults, schema_dir=schema_dir)
    assert "data_path" not in _keys(findings, "WARN")
    assert "model_type" not in _keys(findings, "WARN")


# ------------------------------------------------------------------- types


def test_wrong_scalar_type_is_error(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["optimization_time_step"] = "30"
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "optimization_time_step")[0]
    assert hit.severity == "ERROR"
    assert "int" in hit.message


def test_bool_is_not_accepted_as_int(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["historic_days_to_retrieve"] = True
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "historic_days_to_retrieve")[0].severity == "ERROR"


def test_int_is_accepted_for_float(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["load_peak_hours_cost"] = 1
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "load_peak_hours_cost") == []


def test_select_option_outside_list_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["costfun"] = "cheapest"
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "costfun")[0]
    assert hit.severity == "ERROR"
    assert "profit" in hit.message and "self-consumption" in hit.message


def test_array_element_of_wrong_type_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["nominal_power_of_deferrable_loads"] = [3000.0, "750"]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "nominal_power_of_deferrable_loads")[0]
    assert hit.severity == "ERROR"
    assert "[1]" in hit.message


def test_scalar_where_array_expected_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["nominal_power_of_deferrable_loads"] = 3000.0
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "nominal_power_of_deferrable_loads")[0].severity == "ERROR"


def test_null_value_is_info_not_error(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["weather_forecast_pv_quantile_bias"] = None
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hits = _by_key(findings, "weather_forecast_pv_quantile_bias")
    assert all(f.severity == "INFO" for f in hits)


def test_load_peak_hour_periods_accepts_mapping(
    validate_config_mod, config_defaults, schema_dir
):
    findings = _findings(validate_config_mod, config_defaults, schema_dir=schema_dir)
    assert _by_key(findings, "load_peak_hour_periods") == []


# ------------------------------------------------------ per-load array lengths


def test_short_per_load_array_is_warn(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["number_of_deferrable_loads"] = 3
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "nominal_power_of_deferrable_loads")[0]
    assert hit.severity == "WARN"
    assert "2" in hit.message and "3" in hit.message


def test_long_per_load_array_is_warn(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["nominal_power_of_deferrable_loads"] = [3000.0, 750.0, 500.0]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "nominal_power_of_deferrable_loads")[0]
    assert hit.severity == "WARN"
    assert "ignored" in hit.message.lower()


def test_number_of_deferrable_loads_zero_with_arrays_is_fine(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["number_of_deferrable_loads"] = 0
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert [f for f in findings if f.severity == "ERROR"] == []


# --------------------------------------------------- per-battery array lengths


def test_battery_list_with_wrong_length_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["set_use_battery"] = True
    cfg["number_of_batteries"] = 2
    cfg["battery_nominal_energy_capacity"] = [5000, 5000, 5000]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "battery_nominal_energy_capacity")[0]
    assert hit.severity == "ERROR"
    assert "number_of_batteries=2" in hit.message


def test_battery_scalar_with_multiple_batteries_is_accepted(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["set_use_battery"] = True
    cfg["number_of_batteries"] = 2
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "battery_nominal_energy_capacity") == []


def test_battery_single_element_list_with_one_battery_is_accepted(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["set_use_battery"] = True
    cfg["battery_charge_power_max"] = [1000]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "battery_charge_power_max") == []


def test_battery_scalar_where_schema_says_array_is_not_an_error(
    validate_config_mod, config_defaults, schema_dir
):
    # param_definitions says array.int but upstream broadcasts scalars (#610)
    findings = _findings(validate_config_mod, config_defaults, schema_dir=schema_dir)
    assert _by_key(findings, "battery_discharge_power_max") == []


# ---------------------------------------------------------------- SOC checks


def test_soc_percent_instead_of_fraction_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["battery_minimum_state_of_charge"] = 30
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "battery_minimum_state_of_charge")[0]
    assert hit.severity == "ERROR"
    assert "fraction" in hit.message


def test_soc_min_above_max_is_error(validate_config_mod, config_defaults, schema_dir):
    cfg = copy.deepcopy(config_defaults)
    cfg["battery_minimum_state_of_charge"] = 0.9
    cfg["battery_maximum_state_of_charge"] = 0.3
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert any(
        f.severity == "ERROR" and "battery_maximum_state_of_charge" in f.message
        for f in _by_key(findings, "battery_minimum_state_of_charge")
    )


def test_soc_target_outside_bounds_is_warn(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["battery_target_state_of_charge"] = 0.95
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "battery_target_state_of_charge")[0].severity == "WARN"


def test_soc_per_battery_list_is_checked_elementwise(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["number_of_batteries"] = 2
    cfg["battery_minimum_state_of_charge"] = [0.3, 1.5]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "battery_minimum_state_of_charge")[0]
    assert hit.severity == "ERROR" and "[1]" in hit.message


# -------------------------------------------------------- hybrid inverter #875


def test_hybrid_inverter_with_zero_ac_max_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["inverter_is_hybrid"] = True
    cfg["inverter_ac_output_max"] = 0
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "inverter_ac_output_max")[0]
    assert hit.severity == "ERROR"
    assert "875" in hit.message


def test_hybrid_inverter_zero_ac_input_max_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["inverter_is_hybrid"] = True
    cfg["inverter_ac_input_max"] = 0
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "inverter_ac_input_max")[0].severity == "ERROR"


def test_non_hybrid_inverter_with_zero_ac_max_is_not_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["inverter_is_hybrid"] = False
    cfg["inverter_ac_output_max"] = 0
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert all(
        f.severity != "ERROR" for f in _by_key(findings, "inverter_ac_output_max")
    )


# ------------------------------------------------- semi-continuous operating hours


def test_semi_cont_operating_hours_not_whole_timesteps_is_warn(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["optimization_time_step"] = 30
    cfg["treat_deferrable_load_as_semi_cont"] = [True, True]
    cfg["operating_hours_of_each_deferrable_load"] = [1.25, 0]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    hit = _by_key(findings, "operating_hours_of_each_deferrable_load")[0]
    assert hit.severity == "WARN"
    assert "[0]" in hit.message and "1.5" in hit.message  # ceil(1.25 / 0.5) * 0.5


def test_whole_timestep_operating_hours_produce_no_finding(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["operating_hours_of_each_deferrable_load"] = [4, 2.5]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "operating_hours_of_each_deferrable_load") == []


def test_operating_hours_longer_than_horizon_is_warn(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["delta_forecast_daily"] = 1
    cfg["operating_hours_of_each_deferrable_load"] = [30, 0]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert (
        _by_key(findings, "operating_hours_of_each_deferrable_load")[0].severity
        == "WARN"
    )


# ----------------------------------------------------------- other sanity


def test_end_timestep_before_start_timestep_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["start_timesteps_of_each_deferrable_load"] = [10, 0]
    cfg["end_timesteps_of_each_deferrable_load"] = [5, 0]
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert (
        _by_key(findings, "end_timesteps_of_each_deferrable_load")[0].severity
        == "ERROR"
    )


def test_optimization_time_step_not_dividing_hour_is_warn(
    validate_config_mod, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["optimization_time_step"] = 25
    findings = _findings(validate_config_mod, cfg, schema_dir=schema_dir)
    assert _by_key(findings, "optimization_time_step")[0].severity == "WARN"


# --------------------------------------------------------------- legacy yaml


def test_legacy_sectioned_yaml_is_flattened_and_mapped(
    validate_config_mod, schema_dir, tmp_path
):
    yaml_text = """
retrieve_hass_conf:
  freq: 30
  days_to_retrieve: 2
optim_conf:
  num_def_loads: 1
  P_deferrable_nom: [3000]
plant_conf:
  P_from_grid_max: 9000
"""
    path = tmp_path / "config_emhass.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    cfg, notes = validate_config_mod.load_config(path)
    assert cfg["optimization_time_step"] == 30
    assert cfg["number_of_deferrable_loads"] == 1
    assert cfg["maximum_power_from_grid"] == 9000
    assert any("legacy" in n.lower() for n in notes)


# ----------------------------------------------------------- runtime params


def test_runtime_unknown_key_is_warn(validate_config_mod, config_defaults, schema_dir):
    findings = _findings(
        validate_config_mod,
        config_defaults,
        runtime={"prediction_horizn": 10},
        schema_dir=schema_dir,
    )
    hit = _by_key(findings, "runtime.prediction_horizn")[0]
    assert hit.severity == "WARN"
    assert "prediction_horizon" in hit.message


def test_runtime_forecast_lists_are_known(
    validate_config_mod, config_defaults, schema_dir
):
    runtime = {
        "pv_power_forecast": [0, 100, 200],
        "load_cost_forecast": [0.1, 0.2, 0.3],
        "prod_price_forecast": [0.05, 0.05, 0.05],
        "load_power_forecast": [400, 400, 400],
        "outdoor_temperature_forecast": [10, 11, 12],
    }
    findings = _findings(
        validate_config_mod, config_defaults, runtime=runtime, schema_dir=schema_dir
    )
    assert not [
        f for f in findings if f.key.startswith("runtime.") and f.severity != "INFO"
    ]


def test_runtime_forecast_with_nan_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    runtime = {"pv_power_forecast": [0, None, 200]}
    findings = _findings(
        validate_config_mod, config_defaults, runtime=runtime, schema_dir=schema_dir
    )
    assert _by_key(findings, "runtime.pv_power_forecast")[0].severity == "ERROR"


def test_runtime_soc_init_percent_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    findings = _findings(
        validate_config_mod,
        config_defaults,
        runtime={"soc_init": 55},
        schema_dir=schema_dir,
    )
    assert _by_key(findings, "runtime.soc_init")[0].severity == "ERROR"


def test_runtime_prediction_horizon_below_five_is_error(
    validate_config_mod, config_defaults, schema_dir
):
    findings = _findings(
        validate_config_mod,
        config_defaults,
        runtime={"prediction_horizon": 3},
        schema_dir=schema_dir,
    )
    assert _by_key(findings, "runtime.prediction_horizon")[0].severity == "ERROR"


def test_runtime_config_override_is_type_checked(
    validate_config_mod, config_defaults, schema_dir
):
    findings = _findings(
        validate_config_mod,
        config_defaults,
        runtime={"number_of_deferrable_loads": "two"},
        schema_dir=schema_dir,
    )
    assert (
        _by_key(findings, "runtime.number_of_deferrable_loads")[0].severity == "ERROR"
    )


def test_runtime_per_load_override_is_length_checked_only_for_payload_keys(
    validate_config_mod, config_defaults, schema_dir
):
    runtime = {"operating_hours_of_each_deferrable_load": [4]}
    findings = _findings(
        validate_config_mod, config_defaults, runtime=runtime, schema_dir=schema_dir
    )
    assert (
        _by_key(findings, "runtime.operating_hours_of_each_deferrable_load")[0].severity
        == "WARN"
    )
    assert _by_key(findings, "runtime.nominal_power_of_deferrable_loads") == []


def test_runtime_type_check_uses_runtime_schema(
    validate_config_mod, config_defaults, schema_dir
):
    findings = _findings(
        validate_config_mod,
        config_defaults,
        runtime={"def_current_state": [True, "off"]},
        schema_dir=schema_dir,
    )
    assert _by_key(findings, "runtime.def_current_state")[0].severity == "ERROR"


# -------------------------------------------------------------------- CLI


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_cli_exit_zero_on_clean_config(tmp_path, config_defaults, schema_dir):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config_defaults), encoding="utf-8")
    proc = _run_cli(cfg_path, "--schema-dir", schema_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def test_cli_exit_nonzero_on_error_and_prints_one_finding_per_line(
    tmp_path, config_defaults, schema_dir
):
    cfg = copy.deepcopy(config_defaults)
    cfg["costfun"] = "cheapest"
    cfg["numbr_of_deferrable_loads"] = 2
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    proc = _run_cli(cfg_path, "--schema-dir", schema_dir)
    assert proc.returncode == 1
    lines = [
        ln
        for ln in proc.stdout.splitlines()
        if ln.startswith(("ERROR", "WARN", "INFO"))
    ]
    assert any(ln.startswith("ERROR") and "costfun" in ln for ln in lines)
    assert any(
        ln.startswith("WARN") and "numbr_of_deferrable_loads" in ln for ln in lines
    )


def test_cli_uses_bundled_schema_by_default(tmp_path, config_defaults):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config_defaults), encoding="utf-8")
    proc = _run_cli(cfg_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_runtime_file(tmp_path, config_defaults, schema_dir):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config_defaults), encoding="utf-8")
    rt_path = tmp_path / "runtime.json"
    rt_path.write_text(json.dumps({"prediction_horizon": 2}), encoding="utf-8")
    proc = _run_cli(cfg_path, "--runtime", rt_path, "--schema-dir", schema_dir)
    assert proc.returncode == 1
    assert "runtime.prediction_horizon" in proc.stdout


def test_cli_unreadable_file_exits_two(tmp_path):
    proc = _run_cli(tmp_path / "missing.json")
    assert proc.returncode == 2


@pytest.mark.parametrize("ext", ["json", "yaml"])
def test_cli_accepts_json_and_yaml(tmp_path, config_defaults, schema_dir, ext):
    cfg_path = tmp_path / f"config.{ext}"
    if ext == "json":
        cfg_path.write_text(json.dumps(config_defaults), encoding="utf-8")
    else:
        # minimal YAML written by hand so the test stays stdlib-only
        cfg_path.write_text(
            "costfun: profit\noptimization_time_step: 30\nnumber_of_deferrable_loads: 1\n"
            "nominal_power_of_deferrable_loads: [3000]\n",
            encoding="utf-8",
        )
    proc = _run_cli(cfg_path, "--schema-dir", schema_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
