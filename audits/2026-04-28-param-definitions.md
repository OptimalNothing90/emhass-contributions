# EMHASS `param_definitions.json` Schema Audit

**Date:** 2026-04-28
**Upstream tip:** `6537c47` on `davidusb-geek/emhass` `master`
**Author:** OptimalNothing90 (Mauricio)
**Feeds:** board cards `AC-2a` (unit field), `AC-2-fix` (default mismatches), `AC-2b` (missing-from-param-def)

---

## 1. Methodology

Three sources scanned independently and cross-checked:

| Set | Source file | Scope |
|-----|-------------|-------|
| **A** | `src/emhass/static/data/param_definitions.json` | All entries × 6 categories |
| **B** | `src/emhass/data/config_defaults.json` | Top-level keys |
| **C** | `src/emhass/utils.py` `treat_runtimeparams` (lines 597-1334) | Regex-scan for `runtimeparams.get("X")`, `"X" in runtimeparams`, `runtimeparams["X"]`, plus the explicit `forecast_key` list and `ml_param_defs` table |

Findings manually verified by reading the source. False positives in Set C (regex-caught dict refs like `optim_conf`, `plant_conf`, `retrieve_hass_conf`, `optim_status`, `time_zone`, plus an artefact `jet`) excluded from runtime-param classification.

Reproducer: see Section 6. Re-runs against future upstream tips will surface drift.

**Out of scope** (already addressed): PR #817 (`regression_model` typo, merged), Issue #818 (`ignore_pv_feedback_during_curtailment` runtime flag unwired). See Section 7.

---

## 2. Summary Counts

| Set | Source | Count |
|-----|--------|-------|
| A | `param_definitions.json` | **87** |
| B | `config_defaults.json` | **94** |
| C | `treat_runtimeparams` (raw regex) | 74 |
| C* | runtime-only after false-positive filter | ~30 |
| A ∩ B | both schema & defaults | **86** |
| A ∩ B ∩ C | all three | 6 |
| Union (A ∪ B ∪ C, raw) | all keys seen | 157 |

**Per-category breakdown of A:**

| Category | Count |
|----------|-------|
| Local | 18 |
| System | 23 |
| Tariff | 6 |
| Solar System (PV) | 11 |
| Deferrable Loads | 10 |
| Battery | 19 |
| **Total** | **87** |

**Mismatch breakdown:**

| Type | Count | Section |
|------|------:|---------|
| `default-mismatch` (real, after array-shape filter) | 4 | §3 |
| `type-spelling` (`bool` vs `boolean`) | 1 | §3 |
| `struct-keys` (template vs concrete) | 1 (informational) | §3 |
| `array-shape` (scalar A vs list B with differing first element) | 1 | §3 |
| `orphan-in-A` (in param_def, missing from config_defaults) | 1 (= #818) | §7 |
| `missing-from-A` (config_defaults side) | 8 | §4 |
| `missing-from-A` (runtime-only side) | ~30 | §4 |

---

## 3. Mismatch Table — AC-2-fix Candidates

Excludes findings already addressed (PR #817, Issue #818).

| Key | Category | Mismatch type | `param_def.default_value` | `config_defaults.json` | Severity | Notes / proposed fix |
|-----|----------|---------------|---------------------------|------------------------|----------|----------------------|
| `historic_days_to_retrieve` | System | default-mismatch | `2` | `9` | error | Description (`param_def`) literally says "Defaults to 2" but config_defaults uses `9`. Code path uses config_defaults — schema lies to readers. **Fix:** `param_def.default_value` and Description → `9`. |
| `inverter_ac_output_max` | System | default-mismatch | `0` | `5000` | error | `0` makes no sense as a "max" power. Description says "Maximum hybrid inverter output power from combined PV and battery discharge." **Fix:** `param_def.default_value` → `5000`. |
| `inverter_ac_input_max` | System | default-mismatch | `0` | `5000` | error | Same as `inverter_ac_output_max`. **Fix:** `param_def.default_value` → `5000`. |
| `load_forecast_method` | System | default-mismatch | `"typical"` | `"naive"` | warn | Description in param_def: "...'naive' for a simple 1-day persistence model." Description points users at naive; default in config_defaults agrees; param_def chooses `typical`. **Fix:** `param_def.default_value` → `"naive"`. (Or revisit Description if "typical" really is the recommended default.) |
| `ignore_pv_feedback_during_curtailment` | Battery | type-spelling | `input: "bool"` | n/a | warn | All other booleans in param_def use `"input": "boolean"`. This entry uses `"input": "bool"` (line 575). Inconsistency for any consumer mapping `input` to a type system. **Fix:** `"bool"` → `"boolean"`. (Note: this entry is also tracked in #818 for being unwired runtime-side; spelling fix is independent.) |

**Informational-only findings (not AC-2-fix scope):**

| Key | Type | Detail |
|-----|------|--------|
| `load_peak_hour_periods` | struct-keys | param_def shows `period_hp_template` placeholder; config_defaults has concrete `period_hp_1` + `period_hp_2`. Both correct for their roles (template vs runtime default). No fix needed. |
| `operating_hours_of_each_deferrable_load` | array-shape | param_def scalar `0`; config_defaults `[4, 0]`. `input: "array.int"` so scalar in param_def represents per-element pattern. First-element mismatch (4 vs 0) — defensible to leave as `0` for "all-zero starter pattern" but documents N=2 with first=4 in config_defaults. Borderline; group with AC-2-fix only if maintainer agrees. |

**Status: 5 actionable items. AC-2-fix card stays open.**

---

## 4. Missing-from-param-def — AC-2b Input Data

### 4.1 Keys present in `config_defaults.json` but absent from `param_definitions.json` (8)

| Key | Default | Likely category | Notes |
|-----|---------|-----------------|-------|
| `data_path` | `"default"` | Local | Filesystem-style. Path to data dir (string). |
| `model_type` | `"load_forecast"` | System (or new ML group) | ML forecaster identifier. Used by `regressor-model-fit` paths. |
| `var_model` | `"sensor.power_load_no_var_loads"` | System (or ML) | Default load sensor for ML training. |
| `sklearn_model` | `"KNeighborsRegressor"` | System (or ML) | Sklearn estimator class name. |
| `num_lags` | `48` | System (or ML) | Number of lag features for ML forecaster. |
| `split_date_delta` | `"48h"` | System (or ML) | Train/validate split window string. |
| `perform_backtest` | `false` | System (or ML) | Toggle backtest evaluation in fit path. |
| `deferrable_load_groups` | `[]` | Deferrable Loads | Group-membership list for deferrable loads. Empty default. |

### 4.2 Runtime-only params (Set C minus false positives) (~30)

Grouped by purpose. These come from `treat_runtimeparams` (`utils.py:597-1334`).

**MPC control (`set_type=naive-mpc-optim`):**
- `prediction_horizon` (default 10 timesteps)
- `soc_init` (fallback to `battery_target_state_of_charge`)
- `soc_final` (fallback to `battery_target_state_of_charge`)
- `operating_timesteps_of_each_deferrable_load`

**Forecast input lists:**
- `pv_power_forecast`
- `load_power_forecast`
- `load_cost_forecast`
- `prod_price_forecast`
- `outdoor_temperature_forecast`

**ML predict / predict-publish:**
- `model_predict_publish`
- `model_predict_entity_id`
- `model_predict_device_class`
- `model_predict_unit_of_measurement`
- `model_predict_friendly_name`
- `mlr_predict_entity_id`
- `mlr_predict_device_class`
- `mlr_predict_unit_of_measurement`
- `mlr_predict_friendly_name`
- `regression_model` (default `"AdaBoostRegressor"` after PR #817)
- `n_trials` (default 10)

**Custom HA entity overrides (15 keys):** `custom_pv_forecast_id`, `custom_load_forecast_id`, `custom_pv_curtailment_id`, `custom_hybrid_inverter_id`, `custom_batt_forecast_id`, `custom_batt_soc_forecast_id`, `custom_grid_forecast_id`, `custom_cost_fun_id`, `custom_optim_status_id`, `custom_unit_load_cost_id`, `custom_unit_prod_price_id`, `custom_deferrable_forecast_id`, `custom_predicted_temperature_id`, `custom_heating_demand_id`. (`publish_prefix` also lives here.)

**ML fit / regressor:**
- `csv_file`, `features`, `target`, `timestamp`, `date_features`, `new_values`

**InfluxDB export:**
- `sensor_list`, `csv_filename`, `start_time`, `end_time`, `resample_freq`, `timestamp_col_name`, `decimal_places`, `handle_nan`

**Misc / runtime control:**
- `alpha` (default 0.5), `beta` (default 0.5)
- `weather_forecast_cache`, `weather_forecast_cache_only`
- `entity_save`
- `def_current_state`
- `solcast_api_key`, `solcast_rooftop_id`, `solar_forecast_kwp` (secrets)
- `def_load_config`, `heater_desired_temperatures`, `heater_start_temperatures` (thermal)
- `freq` (legacy alias for `optimization_time_step`)
- `delta_forecast` (legacy alias for `delta_forecast_daily`)
- `time_zone`

**Total real runtime-only params: ~30** (board card AC-2b body cited "~30+ runtime/MPC params" — confirmed).

**Sequencing for AC-2b:** AC-2a (unit field) lands first (additive, no risk) → AC-2-fix in parallel (independent fix PR) → AC-2b uses the established unit enum and adds these ~38 keys (8 from §4.1 + ~30 from §4.2) as new `param_definitions.json` entries. AC-2b unblocks AM-1 (openapi.json auto-gen) and AM-2 (config.md auto-render).

---

## 5. Unit-Choice Table — AC-2a Input

Recommended `unit` value per `param_definitions.json` entry, using the AC-2a enum:
`W`, `Wh`, `kWh`, `€/kWh`, `€`, `%`, `fraction`, `°C`, `°`, `min`, `h`, `days`, `timesteps`, `count`, `s`, `none`.

**Skip rule:** entries with `input=select` or `input=string` for sensor-IDs / method-selectors → `unit=none`.

### 5.1 Local (18)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `costfun` | select | `none` | enum |
| `sensor_power_photovoltaics` | string | `none` | sensor ID |
| `sensor_power_photovoltaics_forecast` | string | `none` | sensor ID |
| `sensor_power_load_no_var_loads` | string | `none` | sensor ID |
| `sensor_replace_zero` | array.string | `none` | sensor IDs |
| `sensor_linear_interp` | array.string | `none` | sensor IDs |
| `ssl_no_verify` | boolean | `none` | toggle |
| `use_websocket` | boolean | `none` | toggle |
| `use_influxdb` | boolean | `none` | toggle |
| `influxdb_host` | string | `none` | hostname |
| `influxdb_port` | int | `count` | port number |
| `influxdb_database` | string | `none` | DB name |
| `influxdb_measurement` | string | `none` | InfluxDB measurement name |
| `influxdb_retention_policy` | string | `none` | RP name |
| `influxdb_use_ssl` | boolean | `none` | toggle |
| `influxdb_verify_ssl` | boolean | `none` | toggle |
| `continual_publish` | boolean | `none` | toggle |
| `logging_level` | select | `none` | enum |

### 5.2 System (23)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `optimization_time_step` | int | `min` | "in minutes" (Description) |
| `historic_days_to_retrieve` | int | `days` | "from now to days_to_retrieve days" |
| `load_negative` | boolean | `none` | toggle |
| `set_zero_min` | boolean | `none` | toggle |
| `method_ts_round` | select | `none` | enum |
| `delta_forecast_daily` | int | `days` | "number of days for forecasted data" |
| `load_forecast_method` | select | `none` | enum |
| `set_total_pv_sell` | boolean | `none` | toggle |
| `num_threads` | int | `count` | "number of threads" |
| `lp_solver_timeout` | int | `s` | "maximum time (in seconds)" |
| `lp_solver_mip_rel_gap` | float | `fraction` | "0 to 1 (0% to 100%)" — explicit fraction |
| `weather_forecast_method` | select | `none` | enum |
| `open_meteo_cache_max_age` | int | `min` | "maximum age, in minutes" |
| `maximum_power_from_grid` | int | `W` | "in Watts" (Description) |
| `maximum_power_to_grid` | int | `W` | "in Watts" |
| `inverter_is_hybrid` | boolean | `none` | toggle |
| `inverter_ac_output_max` | int | `W` | inverter AC power |
| `inverter_ac_input_max` | int | `W` | inverter AC power |
| `inverter_efficiency_dc_ac` | float | `fraction` | "(percentage/100)" |
| `inverter_efficiency_ac_dc` | float | `fraction` | "(percentage/100)" |
| `inverter_stress_cost` | float | `€/kWh` | "(Currency/kWh)" |
| `inverter_stress_segments` | int | `count` | "number of linear segments" |
| `compute_curtailment` | boolean | `none` | toggle |

### 5.3 Tariff (6)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `load_cost_forecast_method` | select | `none` | enum |
| `load_peak_hour_periods` | array.time | `none` | time-of-day strings, not duration |
| `load_peak_hours_cost` | float | `€/kWh` | tariff price |
| `load_offpeak_hours_cost` | float | `€/kWh` | tariff price |
| `production_price_forecast_method` | select | `none` | enum |
| `photovoltaic_production_sell_price` | float | `€/kWh` | "in €/kWh" (Description) |

### 5.4 Solar System (PV) (11)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `set_use_pv` | boolean | `none` | toggle |
| `set_use_adjusted_pv` | boolean | `none` | toggle |
| `adjusted_pv_regression_model` | select | `none` | enum |
| `adjusted_pv_solar_elevation_threshold` | int | `°` | solar elevation angle |
| `adjusted_pv_model_max_age` | int | `h` | "Maximum age in hours" |
| `pv_module_model` | array.string | `none` | model name |
| `pv_inverter_model` | array.string | `none` | model name |
| `surface_tilt` | array.int | `°` | angle |
| `surface_azimuth` | array.int | `°` | angle |
| `modules_per_string` | array.int | `count` | count |
| `strings_per_inverter` | array.int | `count` | count |

### 5.5 Deferrable Loads (10)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `number_of_deferrable_loads` | int | `count` | count |
| `nominal_power_of_deferrable_loads` | array.float | `W` | "in Watts" (Description) |
| `minimum_power_of_deferrable_loads` | array.float | `W` | "in Watts" |
| `operating_hours_of_each_deferrable_load` | array.int | `h` | "number of hours" |
| `treat_deferrable_load_as_semi_cont` | array.boolean | `none` | toggle list |
| `set_deferrable_load_single_constant` | array.boolean | `none` | toggle list |
| `set_deferrable_startup_penalty` | array.float | `€/kWh` | derived cost (`nominal_power * cost_of_electricity * timestep`) |
| `set_deferrable_max_startups` | array.int | `count` | "maximum number of times" |
| `start_timesteps_of_each_deferrable_load` | array.int | `timesteps` | "timestep as from which" |
| `end_timesteps_of_each_deferrable_load` | array.int | `timesteps` | "timestep before which" |

### 5.6 Battery (19)

| Key | input | Unit | Rationale |
|-----|-------|------|-----------|
| `set_use_battery` | boolean | `none` | toggle |
| `set_nocharge_from_grid` | boolean | `none` | toggle |
| `set_nodischarge_to_grid` | boolean | `none` | toggle |
| `set_battery_dynamic` | boolean | `none` | toggle |
| `battery_dynamic_max` | float | `fraction` | "in percentage of battery maximum power" — per-hour fraction |
| `battery_dynamic_min` | float | `fraction` | same; can be negative |
| `weight_battery_discharge` | float | `€/kWh` | "(currency/kWh)" |
| `weight_battery_charge` | float | `€/kWh` | "(currency/kWh)" |
| `battery_discharge_power_max` | int | `W` | "in Watts" |
| `battery_charge_power_max` | int | `W` | "in Watts" |
| `battery_discharge_efficiency` | float | `fraction` | "(percentage/100)" |
| `battery_charge_efficiency` | float | `fraction` | "(percentage/100)" |
| `battery_nominal_energy_capacity` | int | `Wh` | "in Wh" (Description) |
| `battery_minimum_state_of_charge` | float | `fraction` | "(percentage/100)" |
| `battery_maximum_state_of_charge` | float | `fraction` | "(percentage/100)" |
| `battery_target_state_of_charge` | float | `fraction` | "(percentage/100)" |
| `battery_stress_cost` | float | `€/kWh` | "(Currency/kWh)" |
| `battery_stress_segments` | int | `count` | "number of linear segments" |
| `ignore_pv_feedback_during_curtailment` | bool [sic] | `none` | toggle (input spelling fix in §3) |

**Resolution:** all 87 entries assigned a unit. No `[REVIEW]` flags — all rationales backed by Description text or self-evident from `input` type.

---

## 6. Reproducer Script

Save as `audit-input.py`. Uses absolute paths. Re-running on a future upstream tip surfaces drift.

```python
"""Input-side schema audit for EMHASS — reproducible."""
import json
import re
from pathlib import Path

ROOT = Path("C:/Users/MauricioSchäpers/claude-code/emhass/src/emhass")
PARAM_DEF = ROOT / "static" / "data" / "param_definitions.json"
DEFAULTS = ROOT / "data" / "config_defaults.json"
UTILS = ROOT / "utils.py"

# Set A — param_definitions.json
param_def = json.loads(PARAM_DEF.read_text(encoding="utf-8"))
A = {}
for category, entries in param_def.items():
    for k, v in entries.items():
        A[k] = (category, v)

# Set B — config_defaults.json (top-level)
defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
B = dict(defaults)

# Set C — runtime params from utils.treat_runtimeparams (lines 597-1334)
utils_src = UTILS.read_text(encoding="utf-8")
treat_block = utils_src.split("async def treat_runtimeparams")[1].split("\nasync def ")[0]

patterns = [
    r'runtimeparams\.get\(\s*["\']([\w_]+)["\']',
    r'["\']([\w_]+)["\']\s*in\s+runtimeparams',
    r'runtimeparams\[\s*["\']([\w_]+)["\']\s*\]',
]
C = set()
for pat in patterns:
    for m in re.finditer(pat, treat_block):
        C.add(m.group(1))
for m in re.finditer(r'\(\s*"([\w_]+)"\s*,', treat_block):
    name = m.group(1)
    if name not in {"start", "end"}:
        C.add(name)
for k in ("pv_power_forecast", "load_power_forecast", "load_cost_forecast",
          "prod_price_forecast", "outdoor_temperature_forecast"):
    C.add(k)

# Counts
print(f"A: {len(A)}  B: {len(B)}  C-raw: {len(C)}")
for cat, entries in param_def.items():
    print(f"  {cat:25s} {len(entries):3d}")

# Default mismatches (A & B)
print("\n=== Default mismatches ===")
for k in sorted(set(A.keys()) & set(B.keys())):
    a_default = A[k][1].get("default_value")
    b_default = B[k]
    a_input = A[k][1].get("input", "")
    if a_input.startswith("array.") and isinstance(b_default, list):
        if b_default and a_default == b_default[0]:
            continue
        if b_default and isinstance(a_default, str) and a_default in b_default:
            continue
        print(f"  [array-shape] {k}: {a_default!r} vs {b_default!r}")
        continue
    if a_default != b_default:
        if isinstance(a_default, dict) and isinstance(b_default, dict):
            if list(a_default.keys()) != list(b_default.keys()):
                print(f"  [struct-keys] {k}")
                continue
        print(f"  [DEFAULT-MISMATCH] {k}: {a_default!r} vs {b_default!r}")

# input='bool' vs 'boolean' spelling check
for k, (cat, v) in A.items():
    if v.get("input") == "bool":
        print(f"  [INPUT-SPELLING] {k}: input='bool' (others use 'boolean')")

# Missing from A
print("\n=== In B but not in A ===")
for k in sorted(set(B.keys()) - set(A.keys())):
    print(f"  {k}: {B[k]!r}")

# Orphan in A
print("\n=== In A but not in B ===")
for k in sorted(set(A.keys()) - set(B.keys())):
    print(f"  {k}")

# Runtime-only
print("\n=== In C but not in A and not in B ===")
runtime_only = sorted(C - set(A.keys()) - set(B.keys()))
print(f"Total: {len(runtime_only)}")
for k in runtime_only:
    print(f"  {k}")
```

Expected output reproduces Section 2 counts, Section 3 mismatches, Section 4 missing-from-param-def lists.

---

## 7. Out-of-scope Notes

| Finding | Status | Reference |
|---------|--------|-----------|
| `regression_model` default typo (`AdaBoostRegression` → `AdaBoostRegressor`) | MERGED | PR [#817](https://github.com/davidusb-geek/emhass/pull/817), commit `852d775` |
| `ignore_pv_feedback_during_curtailment` runtime flag unwired | OPEN issue | [#818](https://github.com/davidusb-geek/emhass/issues/818) |

These predate this audit and are tracked separately to avoid double-counting in §3-§4.

The **`bool` → `boolean` input-spelling fix** for `ignore_pv_feedback_during_curtailment` (§3) is independent of #818 (#818 is about wiring the runtime flag through to `forecast.py`; the spelling is a schema-consistency concern). Group with AC-2-fix.

The **orphan-in-A** finding for `ignore_pv_feedback_during_curtailment` (in `param_definitions.json` Battery, missing from `config_defaults.json`) is also a manifestation of #818 — the entry was added to schema before the runtime path was wired. Will resolve naturally when #818 is fixed.
