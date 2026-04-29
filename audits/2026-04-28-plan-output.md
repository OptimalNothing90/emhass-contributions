# EMHASS Plan-Output Schema Audit

**Date:** 2026-04-28
**Upstream tip:** `6537c47` on `davidusb-geek/emhass` `master`
**Author:** OptimalNothing90 (Mauricio)
**Feeds:** board card `AC-1` (plan-output schema doc + `emhass_schema_version` constant)

---

## 1. Methodology

Output-side audit of the 5 `_publish_*` helpers in `src/emhass/command_line.py`. Each helper's column set extracted via regex (`cols.append(...)` + `opt_res_latest["..."]`) and confirmed by line-by-line manual read of helper bodies.

| Helper | Lines (verified) | Status |
|--------|------------------|--------|
| `_publish_standard_forecasts` | **2152-2214** | confirmed |
| `_publish_deferrable_loads` | **2215-2259** | confirmed |
| `_publish_thermal_loads` | **2260-2304** | confirmed |
| `_publish_battery_data` | **2305-2341** | confirmed |
| `_publish_grid_and_costs` | **2342-2405** | confirmed |
| Aggregator `publish_data` | starts line **2408**, calls all 5 helpers in order at lines 2464-2468 | confirmed |

Each helper is `async`, takes `(ctx: PublishContext, opt_res_latest: pd.DataFrame)`, returns `list[str]` of published column names (used by aggregator at line 2470 to subset the result DataFrame).

**Sign conventions are NOT guessed.** Each ambiguous column is flagged in §4 as an explicit `[OPEN]` question — better one open question than wrong documentation that has to be retracted.

Reproducer: §5.

---

## 2. Per-helper Summary

### `_publish_standard_forecasts` (line 2152)

Publishes load + PV + curtailment + hybrid-inverter columns. `P_Load` always; `P_PV` only if column present in DataFrame; `P_PV_curtailment` gated on `plant_conf["compute_curtailment"]`; `P_hybrid_inverter` gated on `plant_conf["inverter_is_hybrid"]`. All four use `type_var="power"`.

### `_publish_deferrable_loads` (line 2215)

Loops `range(optim_conf["number_of_deferrable_loads"])`, publishes `P_deferrable{k}` for each. `type_var="deferrable"`. Skips with error log if a column is missing from DataFrame.

### `_publish_thermal_loads` (line 2260)

Helper-of-helper pattern — uses `_publish_thermal_variable` (line 2238) to publish each thermal column. For each `k` where `def_load_config[k]` has `thermal_config` or `thermal_battery`: publishes `predicted_temp_heater{k}` (`type_var="temperature"`) and `heating_demand_heater{k}` (`type_var="energy"`). Conditional: `custom_predicted_temperature_id` must be in `passed_data`.

### `_publish_battery_data` (line 2305)

Gated on `optim_conf["set_use_battery"]`. Publishes `P_batt` (`type_var="batt"`) and `SOC_opt` (`type_var="SOC"`). **HA-scaling trap:** `SOC_opt` is multiplied by **100** at the publish call (line 2329 — `opt_res_latest["SOC_opt"] * 100`) but the column appended to result list (`cols.append("SOC_opt")`) and the underlying DataFrame value remain in fraction (0..1). Downstream consumers reading the CSV get the fraction; HA gets the percent.

### `_publish_grid_and_costs` (line 2342)

Always present. Publishes:
- `P_grid` (`type_var="power"`)
- All columns matching `cost_fun_*` (multi-column, filtered via `[i for i in opt_res_latest.columns if "cost_fun_" in i]`, `type_var="cost_fun"`)
- `optim_status` (`type_var="optim_status"`, defaulted to `"Optimal"` with WARN log if missing — see line 2373-2375)
- `unit_load_cost` (`type_var="unit_load_cost"`)
- `unit_prod_price` (`type_var="unit_prod_price"`)

`optim_status` is published with empty `device_class` and empty `unit_of_measurement` (line 2381-2382) — string column, not numeric.

---

## 3. Column Schema

Single source of truth for downstream consumers. Per-column metadata extracted from the source.

| Column | Source helper | Helper line | Unit | Sign convention | Conditional | HA-scaling | `type_var` | Notes |
|--------|---------------|------------:|------|-----------------|-------------|-------------|------------|-------|
| `P_Load` | `_publish_standard_forecasts` | 2159 | W | positive = consumption (load demand) | always | 1:1 | `power` | DataFrame column read directly |
| `P_PV` | `_publish_standard_forecasts` | 2173 | W | [OPEN: see §4 — likely positive = production] | when `"P_PV"` in DataFrame columns | 1:1 | `power` | `custom_pv_forecast_id` |
| `P_PV_curtailment` | `_publish_standard_forecasts` | 2188 | W | [OPEN: see §4] | `plant_conf.compute_curtailment=true` | 1:1 | `power` | `custom_pv_curtailment_id` |
| `P_hybrid_inverter` | `_publish_standard_forecasts` | 2202 | W | [OPEN: see §4] | `plant_conf.inverter_is_hybrid=true` | 1:1 | `power` | `custom_hybrid_inverter_id` |
| `P_deferrable{k}` | `_publish_deferrable_loads` | 2225 | W | positive = consumption | per `k in range(number_of_deferrable_loads)`; row skipped + error-logged if column missing | 1:1 | `deferrable` | k=0..N-1; `custom_deferrable_forecast_id[k]` |
| `predicted_temp_heater{k}` | `_publish_thermal_loads` (via `_publish_thermal_variable`) | 2247 | °C | n/a (state, not flow) | per `k` where `def_load_config[k]` has `thermal_config` or `thermal_battery` | 1:1 | `temperature` | `custom_predicted_temperature_id[k]` |
| `heating_demand_heater{k}` | `_publish_thermal_loads` (via `_publish_thermal_variable`) | 2247 | **kWh** | [OPEN: see §4 — thermal vs electrical] | same as above | 1:1 | `energy` | unit `"kWh"` confirmed at `utils.py:671`. Note: column called "demand" but unit is energy. `custom_heating_demand_id[k]` |
| `P_batt` | `_publish_battery_data` | 2316 | W | [OPEN: see §4 — charge/discharge sign] | `optim_conf.set_use_battery=true`; row skipped + error-logged if column missing | 1:1 | `batt` | `custom_batt_forecast_id` |
| `SOC_opt` | `_publish_battery_data` | 2329 | **fraction (0..1) in CSV** | n/a (state) | `optim_conf.set_use_battery=true` | **×100 in HA** (% display) | `SOC` | **Scaling trap:** publish call multiplies by 100; DataFrame and result-CSV remain fraction. `custom_batt_soc_forecast_id` |
| `P_grid` | `_publish_grid_and_costs` | 2348 | W | [OPEN: see §4 — import/export sign] | always | 1:1 | `power` | `custom_grid_forecast_id` |
| `cost_fun_<name>` | `_publish_grid_and_costs` | 2362 | € | n/a (cost) | always; multi-column (filter `"cost_fun_"` in name) | 1:1 | `cost_fun` | Components vary by `costfun` choice (`profit`, `cost`, `self-consumption`). Single HA entity `custom_cost_fun_id` aggregates them. |
| `optim_status` | `_publish_grid_and_costs` | 2377 | text | n/a | always (defaulted to `"Optimal"` if missing) | n/a | `optim_status` | values: `"Optimal"`, `"Infeasible"`, `"Unbounded"`, etc. (CVXPY status strings). `device_class=""`, `unit_of_measurement=""` |
| `unit_load_cost` | `_publish_grid_and_costs` | 2394 | €/kWh | n/a (price) | always | 1:1 | `unit_load_cost` | per-timestep tariff series for load |
| `unit_prod_price` | `_publish_grid_and_costs` | 2394 | €/kWh | n/a (price) | always | 1:1 | `unit_prod_price` | per-timestep sell price series |

**Total columns: 11 fixed + variable counts for `P_deferrable{k}`, `predicted_temp_heater{k}`, `heating_demand_heater{k}`, and `cost_fun_<name>` group.**

---

## 4. Sign-Convention Open Questions

Each item is a separate question for `@davidusb-geek` to answer per-line. They are flagged here rather than guessed because mis-documenting a sign convention is worse than asking once.

- **`[OPEN] P_grid` sign convention** — Source: `command_line.py:2348` reads from `opt_res_latest["P_grid"]`. The variable name does not encode direction. Two reasonable conventions exist in the field: positive = import (grid → house, often used in HA energy dashboards) or positive = export (house → grid, often used in PV analytics). Confirm which EMHASS produces.

- **`[OPEN] P_batt` sign convention** — Source: `command_line.py:2316`. The optimisation has separate `p_sto_pos` (discharge contribution to balance) and `p_sto_neg` (charge consumption) variables. The published `P_batt` is presumably their net. Convention: positive = discharge (battery → house) or positive = charge (battery absorbing)?

- **`[OPEN] P_PV`** — Convention proposal: positive = production (PV panels → house). Confirm or correct.

- **`[OPEN] P_PV_curtailment`** — Two interpretations: (a) curtailed delta (positive subtracts from gross PV — "amount we didn't take"), or (b) net post-curtailment PV (the delivered amount after curtailment). Variable name is ambiguous; confirm.

- **`[OPEN] P_hybrid_inverter`** — DC-side or AC-side power? Direction sign? `plant_conf.inverter_is_hybrid` gates the column but the underlying optimisation model is opaque without code-trace into `optimization.py`.

- **`[OPEN] heating_demand_heater{k}`** — Unit is `kWh` (energy), but variable name says "demand". Two interpretations: (a) thermal energy demand (heat the heater needs to deliver), or (b) electrical energy demand (electricity the heater compressor will consume). For COP-based heat pumps these differ by ~factor 3. Critical for downstream consumers building energy dashboards.

- **`[OPEN] predicted_temp_heater{k}`** — Confirm: room temperature, supply-water temperature, or storage-tank temperature? Description not explicit in publish path; needs trace to `optimization.py` thermal model.

Each `[OPEN]` tag = one bullet for David to answer in PR / issue review. Once resolved, §3 table gets the confirmed sign in the appropriate cell and the schema doc proposed in AC-1 ships with confirmed conventions.

---

## 5. Reproducer Script

Save as `audit-output.py`. Re-runs against future tips surface drift in helper bounds + columns.

```python
"""Output-side schema audit — scans the 5 _publish_* helpers in command_line.py."""
import re
from pathlib import Path

CMDLINE = Path("C:/Users/MauricioSchäpers/claude-code/emhass/src/emhass/command_line.py")
src = CMDLINE.read_text(encoding="utf-8")
lines = src.splitlines()

helpers = [
    "_publish_standard_forecasts",
    "_publish_deferrable_loads",
    "_publish_thermal_loads",
    "_publish_battery_data",
    "_publish_grid_and_costs",
]

starts = {}
for h in helpers:
    pat = re.compile(rf"^async def {h}\b")
    for i, ln in enumerate(lines, start=1):
        if pat.search(ln):
            starts[h] = i
            break

sorted_starts = sorted(starts.values())
ranges = {}
for h, s in starts.items():
    nxt = next((n for n in sorted_starts if n > s), len(lines) + 1)
    ranges[h] = (s, nxt - 1)

print("=== Helper line ranges ===")
for h, (s, e) in ranges.items():
    print(f"  {h}: {s}-{e}")

print("\n=== Per-helper columns ===")
for h, (s, e) in ranges.items():
    body = "\n".join(lines[s-1:e])
    cols = set()
    for m in re.finditer(r'cols\.append\(\s*["\']([\w_{}]+)["\']\s*\)', body):
        cols.add(m.group(1))
    for m in re.finditer(r'cols\.append\(\s*f["\']([\w_{}]+)["\']\s*\)', body):
        cols.add(m.group(1))
    df_cols = set(re.findall(r'opt_res_latest\[\s*["\']([\w_]+)["\']\s*\]', body))
    print(f"\n{h}:")
    print(f"  cols.append: {sorted(cols)}")
    print(f"  opt_res_latest reads: {sorted(df_cols)}")

print("\n=== type_var tags ===")
for h, (s, e) in ranges.items():
    body = "\n".join(lines[s-1:e])
    tags = sorted(set(re.findall(r'type_var\s*=\s*["\']([\w_]+)["\']', body)))
    print(f"  {h}: {tags}")

print("\n=== Conditionals ===")
for h, (s, e) in ranges.items():
    body = "\n".join(lines[s-1:e])
    conds = re.findall(r'if\s+(?:not\s+)?(?:ctx\.)?(?:plant_conf|optim_conf|params)\[["\']([\w_]+)["\']\]', body)
    print(f"  {h}: {sorted(set(conds))}")
```

Expected output reproduces §1 line ranges, §3 column lists, helper-conditional summary.

---

## 6. `emhass_schema_version` Proposal

To unblock downstream consumers (Node-RED EVCC adapter, HA cards, EMHASS-troubleshoot skill, future EMHASS-plan-explain skill) versioning their parsers against the published schema, propose a single string constant:

```python
# src/emhass/command_line.py (top-level, near other module constants)
EMHASS_SCHEMA_VERSION = "1.0"
```

Include in result envelope (e.g. add to the dict returned alongside the optimization DataFrame, or attach as DataFrame attribute via `opt_res.attrs["emhass_schema_version"] = EMHASS_SCHEMA_VERSION`). Decide attachment surface in the AC-1 PR — both options are additive and consumer-visible.

**Semver rules:**
- Bump **patch** for documentation-only clarification (sign convention confirmed, descriptions sharpened) — no consumer code change required.
- Bump **minor** for additive columns (new column added without removing or renaming existing). Consumers using `.get(col)` keep working.
- Bump **major** for any of: column removed, column renamed, sign convention flipped, unit changed (e.g. `W` → `kW`), HA-scaling factor changed for a column.

Initial value `"1.0"` because this audit doc is the first formal description of the schema; prior consumer code reverse-engineered columns from source. Locking 1.0 establishes the contract.

---

## 7. Cross-references

- Input-side audit (sibling doc): `docs/superpowers/specs/2026-04-28-param-definitions-audit.md`
- Board card AC-1: `docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json` item `AC-1`
- Maintainer scope corridors: Discussion [#808](https://github.com/davidusb-geek/emhass/discussions/808) (Layers 1-3 + zero-config-default), Issue [#789](https://github.com/davidusb-geek/emhass/issues/789) (EMHASS = MILP, glue layer separate)
- Aggregator entry: `command_line.py:2408` (`publish_data`), helper-call sequence at `2464-2468`
