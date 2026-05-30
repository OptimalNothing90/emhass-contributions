# Runtime / Output Schema Family — Research & Routing Audit

**Date:** 2026-05-29
**Scope:** Durable capture of the full-docs-read + source analysis behind the EMHASS
machine-readable schema family. Feeds **AC-2b** (runtime_params.json), **AC-2c**
(runtime_output.json), **AM-1b** (/action openapi), **AM-7** (config_defaults SoT alignment),
and the openapi generator **AM-1**. Written so none of the 2026-05-29 research is lost and each
item can be picked up cold.

**Sources read (live master 2026-05-29):** `docs/passing_data.md`, `forecasts.md`,
`mlforecaster.md`, `mlregressor.md`, `thermal_battery.md` (51 KB), `thermal_model.md`,
`publish_data.md`, `config.md`, `plan_output_schema.md`, `develop_ai_coders.md`, `develop.md`,
cookbook/* ; `src/emhass/utils.py` `treat_runtimeparams`; `src/emhass/static/configuration_script.js`;
`param_definitions.json` / `config_defaults.json` key diff.

---

## 1. The 4-file schema architecture

EMHASS's machine-readable contract surface splits into four concerns. param_definitions drives
the GUI (`configuration_script.js:130` renders every section as a form field) — so runtime/output
params must NOT go there.

| File | Concern | Status | Consumed by |
|---|---|---|---|
| `src/emhass/static/data/param_definitions.json` | **Config** (startup) form schema | exists | GUI form + AM-1 openapi (config endpoints) |
| `src/emhass/static/data/runtime_params.json` | **Runtime INPUT** optimization knobs | **AC-2b** (new) | AM-1b openapi (/action requestBody) |
| `src/emhass/static/data/runtime_output.json` | **Runtime OUTPUT** routing (publish) | **AC-2c** (new) | AM-1b/publish openapi; cross-refs plan_output_schema.md |
| `docs/api/*.schema.json` (`last-run`, `healthz`) | **Response** schemas | exist (AC-3/AC-4) | AM-1 openapi (response refs) |
| `docs/plan_output_schema.md` | **Output content** (plan DataFrame columns) | exists (AC-1, markdown) | linked via externalDocs (not machine-parsed) |

**openapi composition (AM-1 / AM-1b):** per OpenAPI best practice, applicability is encoded by
**per-operation requestBody composition** (shared `components.schemas` + `$ref`/`allOf` per
`/action/{name}` operation) — NOT a bespoke `applies_to` field in the data files. So the data
files are pure reusable component definitions; the generator composes each action's accepted
subset.

---

## 2. Full runtime-param classification

Every key `treat_runtimeparams` accepts, by bucket → destination. (Counts approximate; the
**completeness gate** — a full `treat_runtimeparams` source scan incl. the `forecast_key` list +
`ml_param_defs` table — must reconcile this before each PR.)

### Bucket A — Runtime-only OPTIMIZATION knobs → `runtime_params.json` (AC-2b)
| key | input | default | unit |
|---|---|---|---|
| `prediction_horizon` | int | 10 | timesteps |
| `soc_init` | float | null→`battery_target_state_of_charge` | fraction |
| `soc_final` | float | null→`battery_target_state_of_charge` | fraction |
| `operating_timesteps_of_each_deferrable_load` | array.int | null | timesteps |
| `alpha` | float | 0.5 | fraction |
| `beta` | float | 0.5 | fraction |
| `weather_forecast_cache` | boolean | false | none |
| `weather_forecast_cache_only` | boolean | false | none |
| `def_current_state` | array.boolean | null | none |
| `def_load_config` | object (externalDocs→thermal_battery.md) | null | none |

**Scan correction (AC-2b completeness gate, PR #915, 2026-05-29):** the source scan moved
`adjusted_pv_model_max_age`, `open_meteo_cache_max_age`, and `time_zone` **out of Bucket A → Bucket C**
— all three are config params already in `param_definitions.json` (+ `config_defaults.json` /
`associations`), NOT runtime-only. **Locked Bucket A = the 10 keys above**, shipped in
`runtime_params.json` via PR #915. Every other runtime key classified; zero unclassifiable.

### Bucket B — OUTPUT routing → `runtime_output.json` (AC-2c)
- `publish_prefix` (string, default "")
- `entity_save` (boolean, default false — persists result entities to `data_path/entities`)
- `continual_publish` (boolean, runtime override of config — include in continual auto-republish loop)
- 15× `custom_*_id` — **nested objects** `{entity_id, device_class, unit_of_measurement, friendly_name}`:
  `custom_pv_forecast_id`, `custom_load_forecast_id`, `custom_pv_curtailment_id`,
  `custom_hybrid_inverter_id`, `custom_batt_forecast_id`, `custom_batt_soc_forecast_id`,
  `custom_grid_forecast_id`, `custom_cost_fun_id`, `custom_optim_status_id`,
  `custom_unit_load_cost_id`, `custom_unit_prod_price_id`, `custom_deferrable_forecast_id` (list),
  `custom_predicted_temperature_id` (list), `custom_heating_demand_id` (list).
  `plan_output_schema.md` maps each result column → its `custom_*_id`.

### Bucket C — Runtime OVERRIDES of existing config params → already in `param_definitions.json`; AM-1b references (NO new entries)
`number_of_deferrable_loads`, `nominal_power_of_deferrable_loads`,
`operating_hours_of_each_deferrable_load`, `start_timesteps_of_each_deferrable_load`,
`end_timesteps_of_each_deferrable_load`, `treat_deferrable_load_as_semi_cont`,
`adjusted_pv_model_max_age`, `open_meteo_cache_max_age`, `time_zone` (all three moved here by the
AC-2b scan — config params, not runtime-only),
`set_deferrable_load_single_constant`, `battery_minimum_state_of_charge`,
`battery_maximum_state_of_charge`, `battery_target_state_of_charge`, `battery_discharge_power_max`,
`battery_charge_power_max`, `lp_solver_timeout`, `lp_solver_mip_rel_gap`, `num_threads`,
`optimization_time_step`.

### Bucket D — Per-call DATA payloads + ML-action args → AM-1b `/action` schema (NOT a config/knob file)
- Forecast lists: `pv_power_forecast`, `load_power_forecast`, `load_cost_forecast`,
  `prod_price_forecast`, `outdoor_temperature_forecast`, `cost_forecast_per_deferrable_load`
- ML forecaster (fit/predict/tune): `historic_days_to_retrieve`, `n_trials`, `model_predict_publish`,
  `model_predict_entity_id`, `model_predict_unit_of_measurement`, `model_predict_friendly_name`
- ML regressor (fit/predict): `csv_file`, `features`, `target`, `regression_model`, `timestamp`,
  `date_features`, `new_values`, `mlr_predict_entity_id`, `mlr_predict_unit_of_measurement`,
  `mlr_predict_device_class`, `mlr_predict_friendly_name`

### Bucket E — §4.1 config keys (in `config_defaults.json`, missing from `param_definitions.json`) → AM-7 SoT alignment
| key | config_defaults default | likely param_def category |
|---|---|---|
| `model_type` | `"load_forecast"` | System / ML |
| `var_model` | `"sensor.power_load_no_var_loads"` | System / ML |
| `sklearn_model` | `"KNeighborsRegressor"` | System / ML |
| `num_lags` | `48` | System / ML |
| `split_date_delta` | `"48h"` | System / ML |
| `perform_backtest` | `false` | System / ML |
| `deferrable_load_groups` | `[]` | Deferrable Loads |
(8th key `data_path` = internal filesystem path — likely NOT user config; exclude or special-case.)
These are config params (loaded at startup) → belong in `param_definitions.json` (config form) per
the SoT rule (param_def first, config_defaults aligns). AM-7 = add these to param_definitions +
keep the shared-default drift-guard test.

### Bucket F — Secrets → never schematized
`solcast_api_key`, `solcast_rooftop_id`, `solar_forecast_kwp`.

### Bucket G — Legacy aliases → documented as aliases, not schematized
`freq` (→`optimization_time_step`), `delta_forecast` (→`delta_forecast_daily`), `def_total_hours` (→`operating_hours_of_each_deferrable_load`).

---

## 3. Per-item scope

- **AC-2b** (SHIPPED, PR #915) → `runtime_params.json` = Bucket A (**10 knobs**, scan-locked). Spec:
  `docs/superpowers/specs/2026-05-29-ac-2b-design.md`. PR-first (user override of Discussion-first).
- **AC-2c** (new card, this audit) → `runtime_output.json` = Bucket B. Nested-object `custom_*_id`
  design + publish_prefix/entity_save/continual_publish. Own brainstorm when picked.
- **AM-1b** (existing card) → openapi `/action` per-operation requestBody composition reading
  runtime_params.json (A) + runtime_output.json (B) + the overridable param_definitions entries (C).
  Action→param map derived from `treat_runtimeparams` `set_type` branches. Gated on AC-4 merge
  (needs openapi.json from AM-1) + AC-2b + AC-2c.
- **AM-7** (existing card) → Bucket E config-key alignment + the shared-scalar drift-guard test
  (param_def↔config_defaults). Gated on agreeing the 7 keys belong in param_definitions.

---

## 4. `def_load_config` — deep thermal sub-schema (do NOT inline)

`def_load_config` is a list (one per deferrable load) of dicts, each empty `{}` or carrying
`thermal_config` (simple direct heater/AC) OR `thermal_battery` (thermal-mass storage / heat pump
/ DHW). `thermal_battery` alone has dozens of keys: supply method (`supply_temperature` +
`carnot_efficiency` / `heating_curve` / `efficiency`), thermal mass (`volume`, `density`,
`heat_capacity`, `thermal_loss`), state (`start_temperature`, `min/max_temperatures`), heating
demand (physics: `u_value`/`envelope_area`/`ventilation_rate`/`heated_volume`/… OR HDD:
`specific_heating_demand`/`area`/… OR DHW: `draw_off_demand`), comfort (`desired_temperatures`,
`overshoot_temperature`, `penalty_factor`, `min_temperature_curve`, `sense`), inertia
(`thermal_inertia_time_constant`, `q_input_initial`). Mutual-exclusion rules apply. → Full schema
lives in `thermal_battery.md`; the JSON schemas reference it via externalDocs, never inline it.
Its own schematization (if ever) is a separate item.

## 5. Conventions (from `develop_ai_coders.md` / `plan_output_schema.md`)

- **Escalation ladder:** PR-direct (<10 lines/docs) / issue-first (behavior, new param) /
  discussion-first (structural, new convention). New schema files are structurally discussion-first;
  AC-2b goes PR-first by user override (PR body justifies + offers alternative).
- **4-step add-a-param (CONFIG):** config_defaults → param_definitions → command_line helper →
  `OptimizationCacheKey` (command_line.py:~108; skip if output-only). Forgetting #4 = cache-miss
  explosion. (Relevant to AM-7's Bucket-E additions.)
- **Semver:** `EMHASS_SCHEMA_VERSION` (plan_output_schema.md): minor = additive field, major =
  remove/rename/type/unit change. The schema-family files align to it.
- **Units:** locked enum `W, Wh, kWh, ¤/kWh, €, %, fraction, °C, °, min, h, days, timesteps, count, s, none`;
  `¤/kWh` machine-field, `currency/kWh` in prose (#867).
- **SOC trap:** fraction (0..1) in DataFrame/CSV and as `soc_init` input; ×100 in HA entity.

## 6. Open questions / borderline

**RESOLVED by the AC-2b completeness scan (PR #915, 2026-05-29):**
- `time_zone` → **Bucket C** (config-override, not runtime-only). Excluded from runtime_params.json.
- `adjusted_pv_model_max_age`, `open_meteo_cache_max_age` → **Bucket C** (config params in param_definitions + config_defaults). Excluded.
- `def_load_config` → **included** in runtime_params.json as a linked opaque object (externalDocs → thermal_battery.md).
- Completeness gate for AC-2b: DONE — full `treat_runtimeparams` scan classified every key, zero unclassifiable, no STOP/pivot.

**Still open (for AC-2c / AM-1b when picked):**
- `continual_publish`: output (Bucket B) vs runtime override of a config param (Bucket C)? Likely B (gates the publish loop) — confirm in AC-2c's scan.
- AC-2c nested-object `custom_*_id` representation (input:object opaque vs defined nested schema).
- AM-1b + AM-7 each run their own completeness re-scan when picked.

---

**Cross-refs:** AC-2b spec `docs/superpowers/specs/2026-05-29-ac-2b-design.md`; predecessor audit
`audits/2026-04-28-param-definitions.md`; OpenAPI best practice (redocly allOf / Stoplight reuse /
learn.openapis parameters). Board: AC-2b, AC-2c (new), AM-1b, AM-7, AM-1.
