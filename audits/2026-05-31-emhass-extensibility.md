# EMHASS Optimizer Extensibility — Effort/Feasibility Assessment

- **Date:** 2026-05-31
- **Method:** Read-only source trace of the local upstream submodule (`upstream/src/emhass/`). No edits, no PRs, no design. Effort ratings = invasiveness of the change to the existing MILP/serving code, not calendar time.
- **Scope:** `optimization.py` (MILP), `web_server.py` (`/action` route), `command_line.py` (optim entry + publish + CSV), `utils.py` (`treat_runtimeparams`). Four prospective builds (a)–(d).
- **Status:** Complete. Sibling-audit line numbers spot-checked and corrected inline (see deltas below).

## Sibling-audit line-number corrections (verified against current source)

| Claim (sibling) | Verified location | Note |
|---|---|---|
| battery scalar vars declared ~801-824 | **`optimization.py:801-824`** | Exact. `p_sto_pos`/`p_sto_neg` (real) + dummy branch + `soc_low/high_recovered`. `E`/`D` binaries at 797-798. |
| battery params scalars ~1136-1144 | **`optimization.py:1136-1147`** | `cap` 1136, effs 1137-1138, max 1139-1140, min/max energy 1143-1144, recovery big-M 1145-1147. |
| SOC accumulation single scalar ~1186-1246 | **`optimization.py:1186-1246`** | `cumsum` 1195, `current_stored_energy = soc_init*cap - cumulative` 1200, recovery band 1205-1240, final-SOC equality 1245-1246. |
| deferrable loads indexed 0..N-1 ~766 | **`optimization.py:766-794`** | `number_of_deferrable_loads` 766; per-load vars appended in loop 772-794. |
| per-load energy constraint ~1899-1922 | **`optimization.py:1899-1922`** | Exact. Big-M relaxed equality on `sum(p)*dt`. |
| target_energy = nominal*hours ~2440-2446 | **`optimization.py:2440 / 2446`** | timestep-based 2440, hours-based 2446. Set as CVXPY Parameter, not rebuilt. |
| grid caps ~747-763, 1011-1016 | **`optimization.py:747-763` and `1011-1016`** | Exact (bounds + D-gated balance). |
| results builder ~2099-2258 | **`optimization.py:2099-2258`** | Exact. `P_batt` 2144, `SOC_opt` 2154, `P_deferrable{k}` 2137. |
| `/action` returns 201 plain-text, CSV | **`web_server.py:600-668`**, dispatch **478-530** | Exact. `opt_res` discarded after `get_injection_dict` (519). CSV write is in `command_line.py` (1446/1532), not web_server. |
| cost scale `0.001*time_step` | **`optimization.py:872`** (obj) / **2180** (results) | Exact. `time_step = freq.seconds/3600` h (78). |

---

## (a) MULTI-STORAGE CO-OPTIMIZATION (home battery + 1..N EV batteries)

### EFFORT: **XL**

The single-battery assumption is woven through variable declaration, the power balance, the SOC recovery state machine, the objective, the results builder, and the runtime/config plumbing. Every one is scalar-per-asset today. This is a structural rewrite of the storage subsystem, not an extension.

### Functions / files touched
- `optimization.py:801-824` — `_initialize_decision_variables`: `p_sto_pos`/`p_sto_neg`/`soc_low_recovered`/`soc_high_recovered` are single `cp.Variable(n)` each, gated on one boolean `set_use_battery`. The dummy-zero else-branch (817-824) also assumes one battery.
- `optimization.py:797-798` — `D`/`E` binaries: `E` is the single charge/discharge direction binary; becomes per-asset.
- `optimization.py:1120-1260` — `_add_battery_constraints`: pulls scalar `cap/eff/max/min` from `plant_conf` (1136-1147), builds the entire SOC trajectory + recovery band (1186-1246) and final-SOC equality (1245-1246) for one asset. Stress cost 1248-1260.
- `optimization.py:962-1016` — `_add_main_power_balance_constraints`: the balance equation (991, 1004, 1008) adds exactly `p_sto_pos + p_sto_neg`. Must sum over assets.
- `optimization.py:1018-1118` — `_add_hybrid_inverter_constraints`: DC-bus balance (1090/1092) hard-wires the single `p_sto_pos/p_sto_neg` onto the DC bus. Multi-asset on a hybrid DC bus is a second open question (which assets are DC-coupled?).
- `optimization.py:846-960` — `_build_objective_function`: cycle-cost penalty (915-930) uses scalar `weight_battery_*` and the single pair. Per-asset weights needed.
- `optimization.py:2140-2158` — `_build_results_dataframe`: emits one `P_batt` (2144) and one `SOC_opt` (2154) reconstructed from the scalar `cap`. Needs `P_batt_{i}`/`SOC_opt_{i}` columns.
- `optimization.py:145-146, 2367-2382` — scalar `param_soc_init`/`param_soc_final` Parameters + the out-of-band gap computation. Becomes per-asset Parameter lists.
- `command_line.py:2248-2283` — `_publish_battery_data`: single `P_batt`/`SOC_opt` publish. Per-asset entity IDs needed.
- `utils.py:931-958` — `soc_init`/`soc_final` runtime injection is scalar (`params["passed_data"]["soc_init"]`). Multi-asset needs list-shaped passed_data + schema.
- Config schema: `config_defaults.json` / `param_definitions.json` battery block is flat scalar (`battery_nominal_energy_capacity`, etc.). Becomes a list-of-assets, which is a SoT-hierarchy change (param_def first per the defaults-SoT memory).

### Concrete changes
- Turn from scalar → list/loop: `p_sto_pos/p_sto_neg` (per asset i), `E` (per asset), `soc_low/high_recovered` (per asset), `param_soc_init/final` + the four recovery params (`_init_soc_recovery_params`, 160-169, becomes per-asset), `cap/eff/max/min` reads (1136-1147 → indexed into a `plant_conf["batteries"][i]`), the cycle-cost terms (927-929), the `P_batt`/`SOC_opt` columns.
- Power balance (991/1004/1008): replace the single `+ p_sto_pos + p_sto_neg` with `+ cp.sum([p_sto_pos[i] + p_sto_neg[i] for i in assets])`.
- The SOC recovery state machine (1205-1240) — currently 10 coupled constraints per battery — must be emitted once per asset; the big-M constants (1145-1147) recomputed per asset capacity.
- Final-SOC equality (1245-1246) per asset.
- `_add_battery_constraints` must loop, or be parameterized by asset index, with grid no-charge/no-discharge couplings (1152-1157) decided per asset or globally.

### Blocked-by / hard parts
- **Hybrid-inverter DC-bus coupling (1090/1092)** is the hard architectural fork: EVs are almost always AC-coupled while the home battery may be DC-coupled. The current code puts the one battery on the DC bus unconditionally. Multi-asset needs a per-asset AC/DC-coupling flag and a re-derivation of the inverter balance — no clean existing seam.
- **Config schema migration** from flat scalars to an asset list touches the param_definitions SoT + config UI render path (the same render path that caused the #869 regression). Non-trivial blast radius.
- EV-specific semantics (availability windows, plug-in/plug-out, deadline SoC) are *not* covered by treating the EV as a plain second battery — see (b).

---

## (b) EV-AS-FLEXIBLE-LOAD WITH STATE-OF-CHARGE (initial→target SoC by deadline, per-slot bounds, variable power)

### EFFORT: option (i) deferrable-load extension = **L**; option (ii) second-battery-with-deadline = **M–L** (and rides on (a)'s blockers if generalized)

This is the gap the sibling audit flagged: deferrable loads have **no SoC state**. They are constrained by a total-energy target (`optimization.py:1899-1922`) and a time window (1945-1955) only — there is no per-slot accumulator and no bound on cumulative energy mid-horizon.

### (i) Extend deferrable loads with an SoC accumulator

**Functions/files touched**
- `optimization.py:1764-2064` — `_add_deferrable_load_constraints`: this is where a new per-load SoC trajectory would be added, mirroring the battery's `cumsum` pattern (1195) but on `p_deferrable[k]`.
- `optimization.py:1899-1922` — the total-energy equality would be *replaced/augmented*: instead of `sum(p)*dt == target`, you want `soc[t] = soc_init + cumsum(p*dt)/cap_ev`, `soc[deadline] >= soc_target`, `soc_min <= soc[t] <= soc_max`.
- `optimization.py:780-784, 1950-1955` — per-load upper bound is a scalar `nominal_power`; variable power min/max already partially exists via `min_power_of_deferrable_loads` (1995-1998) + nominal upper bound, so variable-power EV charging is **already representable** for a continuous load. Good news.
- `optimization.py:171-241` — `_init_deferrable_load_params`: add per-load `param_ev_soc_init`, `param_ev_target`, `param_ev_deadline_mask`, `param_ev_capacity` alongside the existing `param_target_energy` list (198-206). This matches the established warm-start Parameter idiom exactly.
- `optimization.py:2099-2258` — results builder: add `SOC_ev{k}` column (reconstruct like SOC_opt at 2154).
- `utils.py:595-1009` / `959-964` — runtime injection: `operating_timesteps_of_each_deferrable_load` already flows through (`utils.py:959-964`, consumed `command_line.py:1504`). Add `ev_soc_init/ev_target_soc/ev_deadline` to passed_data + a `def_load_config`-style block (the `def_load_config` injection at `utils.py:985-1009` is the natural carrier).
- Config: a new `ev_config` sub-block per deferrable load, analogous to `thermal_config`/`thermal_battery` (already a precedent at `optimization.py:246-321`).

**Concrete changes**
- New per-load SoC accumulator: `ev_soc = soc_init*cap + cp.cumsum(p_deferrable[k]*eff*dt)`; bound `ev_soc <= soc_max*cap` and `ev_soc[deadline:] >= soc_target*cap` (or terminal `ev_soc[-1] >= target`).
- Keep the time-window mask (1950-1955) as the plug-in availability window — it already forces `p=0` outside the window, which is exactly EV-plugged-out semantics.
- The energy-target constraint (1899-1922) becomes redundant for EV loads and should be branched off (like thermal loads already are at 1899-1904 via `is_thermal_load`/`is_thermal_battery` guards). Add an `is_ev_load` guard.

**Blocked-by / hard parts**
- Nothing structurally blocked — this reuses the deferrable-load loop, the Parameter warm-start idiom, and the existing window mask. The energy semantics map cleanly to a cumulative-energy constraint.
- Charging efficiency / one-directional only (no V2G) — fits a deferrable load (nonneg power) perfectly. **V2G (discharge) does NOT fit** deferrable loads (they're `nonneg=True`, `optimization.py:780`) — that needs option (ii).

### (ii) Treat the EV as a second battery with a deadline-SoC constraint

**Functions/files touched** — same set as (a)'s battery path, but for *one* extra asset: `optimization.py:801-824` (vars), `1120-1260` (constraints), `962-1016` (balance), `2140-2158` (results), `145-146`/`2367-2382` (SoC params).

**Concrete changes**
- The only *new* constraint vs. an ordinary battery is a deadline: `current_stored_energy[deadline] >= soc_target*cap` — a single added constraint in `_add_battery_constraints` and an availability mask forcing `p_sto_pos=p_sto_neg=0` while unplugged.
- Gets V2G for free (battery vars are bidirectional).

**Blocked-by / hard parts**
- Inherits (a)'s single-battery hardcoding: the second asset requires the list-ification of `_add_battery_constraints` / balance / results. So "EV as second battery" is only **M** if done as a bespoke second scalar asset (copy-paste the battery block with an availability mask + deadline), but **L–XL** if done generally (= build (a)).
- The recovery state machine (1205-1240) is overkill/awkward for an EV (out-of-band SoC recovery semantics don't match a car).

**Recommendation:** (i) is the lower-invasiveness path for charge-only EV and reuses the most-tested code path (deferrable loop + Parameter idiom). (ii) is preferable only if V2G is a hard requirement, and then it forces (a)'s multi-battery refactor.

---

## (c) JSON-RETURNING OPTIMIZATION ENDPOINT

### EFFORT: **S**

`opt_res` is a fully-formed `pd.DataFrame` in hand at the dispatch site; it is currently thrown away after building the HTML injection dict. Serializing it to JSON in the response body is mechanical.

### Functions / files touched
- `web_server.py:515-521` — `_handle_action_dispatch`, optim branch: `opt_res = await optim_actions[action_name](...)` (518) → `get_injection_dict(opt_res)` (519) → returns a fixed plain-text string (521). `opt_res` is otherwise discarded here.
- `web_server.py:651-668` — `action_call`: takes `(msg, status)` and wraps in `make_response`. The response contract is `(str, int)`.
- `command_line.py:1434-1463` (`dayahead_forecast_optim`) and `1513-1535` (`naive_mpc_optim`): these *return* the DataFrame and *also* persist it via `opt_res.to_csv(...)` (1446 / 1532). `perfect_forecast_optim` likewise at 1244. The DataFrame is the canonical artifact; CSV is a side-effect for `publish_data` to re-read (`command_line.py:2074` `_load_opt_res_latest`).

### Current flow of opt_res
`perform_*_optim` (optimization.py) builds DataFrame via `_build_results_dataframe` (2099) → returned to `command_line.*_optim` → written to `opt_res_latest.csv` (1446/1532) AND returned → `web_server._handle_action_dispatch` (518) uses it only for the HTML injection dict (519) → response is a constant 201 ack string. No pickle of opt_res itself (pickle is used only for the injection dict, `web_server.py:593-597`, and ML models).

### Concrete changes (minimal)
- In `_handle_action_dispatch` optim branch (515-521): after building the injection dict, serialize `opt_res` — `opt_res.reset_index().to_json(orient="records", date_format="iso")` (or `to_dict`) — and return it as the body with `content-type: application/json`, gated behind a query/runtime flag (e.g. `?format=json`) to preserve the existing plain-text contract for HA.
- In `action_call` (663-668): when the flag is set, `make_response(json_body, 201)` with the JSON content-type header instead of the plain-text branch.
- Index handling: `opt_res` is tz-aware DatetimeIndex; `to_json` needs `reset_index()`/`date_format="iso"` so the timestamp survives. NaN→null handling: `to_json` already emits `null`.

### Blocked-by / hard parts
- None functionally. Watch-outs only: (1) the existing 201/plain-text contract is consumed by HA REST commands — must stay default, JSON behind a flag; (2) `optim_status` column (2210) and any NaN columns must serialize cleanly; (3) response size (a 48-slot × ~30-col frame is small, fine). No missing EMHASS capability.

---

## (d) EVOPT-CONTRACT-COMPATIBLE MAPPING LAYER

### EFFORT: **L** for the mechanical mapping shell; **the capability gaps it exposes are XL** (they ARE builds (a)/(b)).

The mapping itself (rename fields, convert units, reshape) is glue. What it cannot do is synthesize EMHASS capabilities that don't exist — per-slot SoC goal, multi-battery, and a variable-`dt[]` horizon.

### Where it would live
- **Best fit: a new module** (e.g. `src/emhass/evopt_adapter.py`) invoked from `web_server.action_call` *before* `set_input_data_dict` (so it produces an EMHASS `runtimeparams` dict) and *after* `_handle_action_dispatch` (to reshape `opt_res` → evopt `OptimizationResult`). It should NOT live inside `treat_runtimeparams` (`utils.py:595`) — that function is already a 700+-line god-function and mixing a foreign contract into it worsens the #869-class fragility.
- The input side leverages the existing runtime-injection surface: `treat_runtimeparams` already accepts arbitrary `optim_conf`/`plant_conf` overrides via `associations.csv` (`utils.py:773-779`), special-cased power-limit vectors (786-810), `optimization_time_step`/`freq` (814-823), forecast lists (`list_forecast_key`, utils.py:1009-1025), `soc_init`/`soc_final` (931-958), and `def_load_config` (985-1009). So the adapter's job on input is: produce a JSON `runtimeparams` blob in EMHASS's vocabulary. The output side reuses (c)'s JSON serialization.

### Mechanical (doable now)
- **dt seconds → minutes scalar:** evopt `dt[]` is a seconds array; EMHASS uses one scalar minute step (`optimization_time_step`, injected at `utils.py:814-818`; `time_step = freq.seconds/3600` h at `optimization.py:78`). If evopt's `dt[]` is *uniform*, divide by 60 → scalar minutes. Mechanical.
- **Wh ↔ W using dt:** evopt energy (Wh) ↔ EMHASS power (W). `Wh = W * dt_hours`; `dt_hours = time_step` (optimization.py:78). Per-slot multiply. Mechanical.
- **currency/Wh ↔ EUR/kWh:** EMHASS cost factor is `0.001*time_step` (optimization.py:872) i.e. it consumes EUR/kWh price arrays (`var_load_cost`/`var_prod_price` columns). `EUR/kWh = (currency/Wh) * 1000`. Mechanical scalar conversion on the price forecast arrays.
- **Field rename** OptimizationInput → forecast lists (`load_cost_forecast`, `prod_price_forecast`, `pv_power_forecast`, `load_power_forecast`) injected via the forecast-key path (utils.py:1009-1025). Mechanical.
- **Result reshape:** `opt_res` columns (`P_grid`, `P_batt`, `SOC_opt`, `P_deferrable{k}`, optimization.py:2123-2154) → evopt `OptimizationResult`. Power W → energy Wh via `*dt`. Mechanical given (c).

### Blocked by missing EMHASS capability (NOT mechanical)
- **Per-slot SoC goal / SoC trajectory bounds:** evopt expresses per-slot SoC targets/bounds. EMHASS battery has only scalar `soc_init`/`soc_final` (optimization.py:145-146, 2367-2382) + a hard min/max band — there is **no per-slot SoC goal input**. For an EV expressed as a flexible load, EMHASS has **no SoC at all** (the gap in (b)). → **Blocked on (b).**
- **Multi-battery:** evopt models multiple storage assets; EMHASS is single scalar battery. → **Blocked on (a).**
- **Variable `dt[]` (non-uniform horizon):** EMHASS hardcodes a single uniform `freq`/`time_step` (optimization.py:76-78, used as a scalar multiplier throughout the SOC accumulation 1192, energy targets 2440/2446, cost 872). A non-uniform `dt[]` array is **not representable** without threading a per-slot `dt` vector through every `*self.time_step` site. → **XL, effectively a horizon-model rewrite.** If evopt only ever sends uniform dt, this collapses to mechanical; if it sends genuinely variable dt, it's blocked.

### Effort
- Adapter shell + uniform-dt + unit conversions + result reshape (assuming (c) lands): **L**.
- Full evopt parity (per-slot SoC, multi-battery, variable dt): gated entirely on (a)+(b)+variable-dt rewrite → **XL**, not an adapter concern.

---

## Effort summary

| Build | Effort | Main blocker | Depends on |
|---|---|---|---|
| (a) Multi-storage co-opt | **XL** | Single-battery hardcoding across vars/balance/SOC-recovery/results + hybrid DC-bus coupling (`optimization.py:1090/1092`) + config-schema migration | — (foundational) |
| (b-i) EV-as-flex-load + SoC | **L** | No SoC accumulator on deferrable loads today; charge-only (no V2G) | reuses deferrable loop + Parameter idiom; independent of (a) |
| (b-ii) EV-as-2nd-battery + deadline | **M** bespoke / **L–XL** general | Inherits (a)'s single-battery scalar hardcoding; recovery state machine ill-fitting for EV | (a) if generalized |
| (c) JSON optim endpoint | **S** | None — `opt_res` DataFrame already in hand at `web_server.py:518`, discarded | — |
| (d) evopt mapping layer | **L** shell / **XL** parity | Per-slot SoC goal, multi-battery, variable `dt[]` are missing EMHASS capabilities, not mapping bugs | (c) for output; (b) for SoC goal; (a) for multi-battery |

## BOTTOM LINE — sequencing

1. **(c) first, standalone.** S-effort, zero dependencies, and it is the output half of (d). Ship the JSON endpoint behind a `?format=json` flag and the contract leak risk to HA stays nil.
2. **(b-i) next.** L-effort, *independent of (a)*, reuses the most-tested code path (deferrable loop + warm-start Parameter idiom), and closes the SoC-goal gap that (d) needs. This is the highest value-per-invasiveness item and the right way to model a charge-only EV. Avoid (b-ii) unless V2G is a hard requirement.
3. **(d) as a thin adapter module** once (c)+(b-i) exist — but only commit to it if evopt's `dt[]` is **uniform**. Verify that first; a genuinely variable `dt[]` is a horizon-model rewrite that no adapter can paper over.
4. **(a) last and only if multi-storage / V2G is genuinely required.** It is the foundational refactor everything heavy hangs off, and its single hardest knot is the **hybrid-inverter DC-bus coupling** (`optimization.py:1090/1092`), which has no clean seam for AC-coupled EVs alongside a DC-coupled home battery.

**Single hardest blocker across all four:** the hybrid-inverter DC-bus coupling in `_add_hybrid_inverter_constraints` (`optimization.py:1090/1092`) — it hard-wires the one battery onto the DC bus, and there is no existing abstraction for per-asset AC/DC coupling, which is exactly what multi-storage (a) and a V2G EV (b-ii) require.
