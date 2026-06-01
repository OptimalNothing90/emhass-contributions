# EMHASS-side verification — EMHASS as the optimization brain behind evcc

- **Date:** 2026-05-31
- **Method:** read-only source audit of the EMHASS submodule at `upstream/src/emhass/`
- **Scope:** confirm/refute capability claims for an "EMHASS-as-planner / evcc-as-executor" coordination concept
- **Status:** COMPLETE (one of three verification streams; siblings: `2026-05-31-evcc-side-verification.md`, `2026-05-31-contributions-evcc-context.md`)

Context: evcc would report a demand (home battery + EV(s) + grid prices + PV forecast + home load) and expect an optimal per-slot schedule back. This audit establishes what EMHASS can and cannot model today.

---

## Claim 1 — Storage count: single or multiple batteries?

**VERDICT: REFUTED (single battery only, hardcoded).**

Decision variables are declared once as single scalar-bounded vectors, not in a loop over storage units. `optimization.py:801-824` (`_initialize_decision_variables`):

```python
if self.optim_conf["set_use_battery"]:
    vars_dict["p_sto_pos"] = cp.Variable(n, nonneg=True, name="p_sto_pos")
    constraints.append(vars_dict["p_sto_pos"] <= self.plant_conf["battery_discharge_power_max"])
    vars_dict["p_sto_neg"] = cp.Variable(n, nonpos=True, name="p_sto_neg")
    constraints.append(vars_dict["p_sto_neg"] >= -np.abs(self.plant_conf["battery_charge_power_max"]))
```

Exactly one `p_sto_pos`, one `p_sto_neg`, one `E` (binary direction), one `SOC_opt` trajectory. Battery params are all scalars from `plant_conf` (`optimization.py:1136-1144`): `battery_discharge_power_max`, `battery_charge_power_max`, `battery_nominal_energy_capacity`, `battery_minimum_state_of_charge`, `battery_maximum_state_of_charge`. No list/loop over multiple storages anywhere in optimization or in `config_defaults.json` / `param_definitions.json`. SOC accumulation (`optimization.py:1186-1246`) uses a single scalar `cap` and `soc_init`. **Adding home battery + EV battery as separate assets requires new variable vectors, a SOC trajectory per storage, and a revised power-balance equation.**

## Claim 2 — EV modeling: deferrable load, battery, or unsupported?

**VERDICT: NUANCED — can partially model an EV, with significant constraints.**

Deferrable loads are indexed `0..N-1` (`number_of_deferrable_loads`, `optimization.py:766`). Each load `k`: power var `p_deferrable[k]` (continuous, nonneg, bounded by nominal), binaries `p_def_bin1/bin2/start`, optional constraints.

Configurable params (`param_definitions.json:402-455`): `nominal_power_of_deferrable_loads` (scalar fixed power or list = fixed profile), `minimum_power_of_deferrable_loads`, `operating_hours_of_each_deferrable_load`, `start_timesteps_of_each_deferrable_load` / `end_timesteps_of_each_deferrable_load`, `treat_deferrable_load_as_semi_cont` (true → binary on/off at nominal; false → continuous variable power), `set_deferrable_load_single_constant` (one contiguous block), `set_deferrable_startup_penalty`, `set_deferrable_max_startups`.

Energy constraint (`optimization.py:1899-1922`):
```python
total_energy_expr = cp.sum(p_deferrable[k]) * self.time_step
constraints.append(total_energy_expr >= self.param_target_energy[k] - M_energy * (1 - self.param_energy_active[k]))
constraints.append(total_energy_expr <= self.param_target_energy[k] + M_energy * (1 - self.param_energy_active[k]))
```
with `param_target_energy[k] = nominal_power * operating_hours` (`optimization.py:2440-2446`).

**CAN express:** variable power per slot (continuous, `min_power..nominal`) when `treat_..._semi_cont=false`; a time window `[start_ts, end_ts]`; a total energy target; a min-power floor (min charge current); a startup penalty. → maps reasonably to "charge X kWh by slot T, power between P_min and P_max."

**CANNOT express:**
1. Target energy independent of nominal_power×hours — target is *derived* from configured nominal power, not set freely. An EV "add 25 kWh at 1.4–11 kW" needs `operating_hours` set so the product matches → only via runtime override.
2. **No SoC-state tracking** — unlike the home battery (`SOC_opt`), a deferrable load only accumulates energy. No "EV at 40% → 80%" concept.
3. No per-slot SoC ceiling/floor for the EV.
4. The list-`nominal_power` "sequence" subtype enforces a *fixed power profile* shifted in time (`optimization.py:1811-1844`, `cp.sum(y)==1`) — more rigid, not flexible.
5. No plug/unplug (present/absent) awareness.

**Bottom line on EV:** deferrable load with `semi_cont=false`, `minimum_power>0`, start/end window, `operating_hours` as energy proxy is the closest existing fit — but no SoC model, not a true "reach SoC by deadline," and no joint energy budget with the home battery.

## Claim 3 — Roadmap-gap features (things evopt does NOT yet do)

- **(a) Grid feed-in / export power limit — CONFIRMED.** `maximum_power_to_grid` (default 9000 W), hard per-slot export cap, time-varying array capable. `optimization.py:750-758,1011-1016`: `constraints.append(-p_grid_neg <= cp.multiply(max_power_to_grid_arr, (1 - D)))`.
- **(b) Grid import / consumption limit — CONFIRMED.** `maximum_power_from_grid` (default 9000 W), hard per-slot import cap. `optimization.py:747-763,1012-1013`: `p_grid_pos <= cp.multiply(max_power_from_grid_arr, D)`.
- **(c) Per-load priorities / sequencing — REFUTED.** No priority ranking. Only `deferrable_load_groups` (`optimization.py:2066-2097`): shared power budget (`sum<=max`) + mutual exclusion (`sum(bin2)<=1`). That's capacity management, not "A only runs if B can't" / ordering. Indirect only via startup penalty.
- **(d) PV AC / inverter limitation — CONFIRMED (hybrid only).** `inverter_is_hybrid=true` activates DC/AC split (`optimization.py:1018-1118`), `inverter_ac_output_max` (default 5000 W) caps AC output: `p_dc_ac <= is_dc_sourcing * p_dc_ac_max`. Standard (non-hybrid) inverters: no hard clip, only optional `compute_curtailment` variable.

## Claim 4 — REST API as optimizer service

**VERDICT: CONFIRMED endpoint exists — but response is a string ack, NOT a JSON schedule.**

`web_server.py:600-668`: `@app.route("/action/<action_name>", methods=["POST"])`. Actions (`web_server.py:509-513`): `perfect-optim`, `dayahead-optim`, `naive-mpc-optim`.

Request: POST JSON runtime params. Injectable (`utils.py:1009-1015`): `pv_power_forecast` (W/slot), `load_power_forecast` (W/slot), `load_cost_forecast` (€/kWh/slot), `prod_price_forecast` (€/kWh/slot), `outdoor_temperature_forecast`; plus `soc_init`, `soc_final`, `prediction_horizon` (MPC), `operating_hours_of_each_deferrable_load`, `start/end_timesteps_of_each_deferrable_load`, `maximum_power_from_grid`, `maximum_power_to_grid` — all overridable at call time.

Response: HTTP 201 plain text `"EMHASS >> Action dayahead-optim executed...\n"`. The result DataFrame is written to `opt_res_latest.csv` + an `injection_dict` pickle for the UI. To retrieve the schedule: read the CSV, or call `publish-data` (pushes per-sensor values to HA). **No endpoint returns the schedule as JSON in the HTTP body.**

Result columns (`_build_results_dataframe`, `optimization.py:2099-2258`): `P_PV`, `P_Load`, `P_grid_pos/neg/`, `P_grid`, `P_deferrable{k}`, `P_batt` (W, +=discharge), `SOC_opt` (fraction 0–1), `unit_load_cost`, `unit_prod_price`, `cost_*`, `maximum_power_from_grid`, `maximum_power_to_grid`, `optim_status`.

## Claim 5 — Units & granularity

**VERDICT: CONFIRMED.** Power = W (`param_definitions.json:80`). Price = €/kWh (`param_definitions.json:303`; cost factor `0.001*time_step`, `optimization.py:872`). Timestep = `optimization_time_step` minutes (default 30; alias `freq`; `param_definitions.json:115-119`, `utils.py:816-819`). Horizon = `delta_forecast_daily` days (default 1) for dayahead, `prediction_horizon` timestep-count (default 10) for MPC; multi-day loops day-by-day (`optimization.py:2794-2843`).

---

## BOTTOM LINE

EMHASS already offers a callable HTTP optimizer (`POST /action/dayahead-optim`) consuming per-slot PV/load/price vectors and producing a full-horizon schedule (grid import/export W, battery SoC, per-deferrable power). It has working hard grid export/import caps and a hybrid-inverter AC limit. Time step configurable (default 30 min).

**Concrete EMHASS-side build gaps for evcc integration:**
1. **No multi-storage** — one battery only. Home battery + EV battery as separate optimizable assets = non-trivial MILP extension (new vars, SOC trajectory per storage, revised power balance).
2. **No EV SoC model in deferrable loads** — can approximate "X kWh in window at variable power" but no initial/target SoC, no per-slot SoC bounds. "40%→80% by 07:00" not expressible.
3. **HTTP response returns no JSON schedule** — 201 is a text ack; schedule lives in CSV / HA publish. An evcc-facing API needs a new endpoint returning `opt_res_latest` as JSON.
4. **No ordered load priorities** — only group mutual exclusion.

**Key files:** `optimization.py` (battery vars 801-824; SOC 1120-1260; deferrable 1764-2064; grid limits 747-763,1011-1016; results 2099-2258); `web_server.py` (action route 600-668; runtime params 437-476); `utils.py` (`treat_runtimeparams` 595-1250; columns 1374-1498); `command_line.py` (`naive_mpc_optim` ~1460-1549; `publish_data` 2351-2413); `static/data/param_definitions.json`; `data/config_defaults.json`.
