# evopt Optimizer Model — Deep-Read Audit

**Date:** 2026-05-31
**Method:** Read-only source review via `gh api` (raw blobs) of `evcc-io/optimizer` @ `main` (tree sha `b5cbfeb`). No clone, no writes to the target repo. Evidence quoted with `file:line` from the fetched blobs.
**Scope:** `src/optimizer/optimizer.py` (MILP model, 622 lines), `src/optimizer/app.py` (API → model mapping), `openapi.yaml`, `README.md`, `test_cases/*.json` (semantics from real inputs).
**Status:** Complete. Every numbered section carries a CONFIRMED / REFUTED / NUANCED verdict plus quoted code. One framing assumption in the task brief (a `Type vehicle/battery` field, `availability windows`, `c_min/c_max` time-varying) is **REFUTED by source** — see §1.
**Stack:** Python + PuLP (CBC solver), single MILP. `pulp.LpProblem("EV_Charging_Optimization", pulp.LpMaximize)` (`optimizer.py:112`) — the model **maximizes** economic benefit (cost terms enter negative).

---

## 1. EV-as-battery flexibility: how is a vehicle distinguished from a stationary battery?

**VERDICT: REFUTED (as framed) / NUANCED.** There is **no `Type` field and no `vehicle`/`battery` enum anywhere** in the model, the dataclass, the API model, or the OpenAPI schema. There are no explicit availability windows and no `c_min`/`c_max` time-series. evopt models **everything as one homogeneous `battery`**. "EV-ness" is **emergent**, expressed entirely through *which scalar/array fields a given battery entry carries*. EMHASS-side framing of a typed vehicle object does not match evopt.

The complete battery contract (`optimizer.py:24-38`):

```python
@dataclass
class BatteryConfig:
    charge_from_grid: bool
    discharge_to_grid: bool
    s_capacity: float
    s_min: float
    s_max: float
    s_initial: float
    c_min: float
    c_max: float
    d_max: float
    p_a: float
    p_demand: Optional[List[float]] = None  # Minimum charge demand (Wh)
    s_goal: Optional[List[float]] = None    # Goal state of charge (Wh)
    c_priority: int = 0
```

`c_min`/`c_max`/`d_max` are **scalars (W)**, not arrays — there is no time-varying power envelope. Only `p_demand[]` and `s_goal[]` are per-slot arrays.

**How EV behaviour is actually expressed** (confirmed from `test_cases/`):
- An EV that must reach a target by a deadline → set `s_goal[t] = target_Wh` at the deadline slot, `0` elsewhere. Example `010-infesible-charge-goal`: `s_goal` is `0` everywhere except slot 9 = `68800`, with `d_max=0` and `charge_from_grid=true`.
- An EV with a per-slot minimum charge profile → `p_demand[]` (Wh per slot). Example `011-infeasible-charge-demand`: `p_demand = [1380,1380,1380,...]`, `d_max=0`.
- A **stationary battery** in the same request carries neither `s_goal` nor `p_demand`, and has `d_max > 0` (it can discharge). In `011`/`012`, BAT1 has `d_max=800`, no goal/demand, `charge_from_grid` unset.

**Plug-in / availability representation — NUANCED.** There is **no `p_a` plug-in flag and no availability bitmap**. (`p_a` in this model is *not* "plugged-in availability" — it is the end-of-horizon monetary value of stored energy, see §4/§5.) Availability is encoded implicitly: a slot where the EV is *unavailable* is expressed by the caller setting that battery's charge ceiling to zero for that slot **only via the SoC-evolution chain** — but since `c_max` is a scalar, evopt has **no native per-slot "car is unplugged"** lockout. The caller (evcc) must instead simply *not* place demand/goal in unavailable slots, and rely on `s_goal`/`p_demand` shaping. There is no constraint that forbids charging in a given slot for an EV that has driven away.

> **EMHASS-relevant gap (evopt weakness):** evopt cannot natively express "vehicle is disconnected for slots 5–12, then reconnected." A drop-in replacement that wants to model intermittent plug-in must emulate it through goal/demand placement, not a first-class availability window. EMHASS's `def_load_config` deferrable-load timing windows are *richer* here.

---

## 2. Time / horizon: dt[], number of slots, energy↔power conversion

**VERDICT: CONFIRMED — fully variable per-slot width.** `dt[]` is a per-slot duration in **seconds** and slot widths may differ within one request. Horizon length is implicit = `len(gt)`.

```python
# optimizer.py:42-47
@dataclass
class TimeSeriesData:
    dt: List[int]  # time step length [s]
    gt: List[float]  # Required total energy [Wh]
    ft: List[float]  # Forecasted production [Wh]
    p_N: List[float]  # Import prices [currency unit/Wh]
    p_E: List[float]  # Export prices [currency unit/Wh]
```

```python
# optimizer.py:72-74
self.T = len(time_series.gt)
self.time_steps = range(self.T)
```

All other arrays must match `len(gt)` or the API 400s (`app.py:182-197`: `if len(set(lengths)) > 1: api.abort(400, ...)`).

**Variable width is real, not theoretical.** Test `016` opens with `dt = [328, 3600, 3600, ...]` (first slot 328 s, rest 1 h, 47 slots total) — confirming evcc sends a short "current partial slot" then hourly slots.

**Power→energy conversion** uses `dt[t]/3600` to turn a power limit (W) into a per-slot energy bound (Wh). Charge/discharge/SoC are all stored as **energy (Wh)**:

```python
# optimizer.py:127-129  (charge var upper bound = c_max[W] * dt/3600 → Wh)
pulp.LpVariable(f"c_{i}_{t}", lowBound=0, upBound=bat.c_max * self.time_series.dt[t] / 3600.)
```

Grid power limits convert the same way (`optimizer.py:382`, `:399`). The demand-rate peak constraint divides energy back to power via `dt/3600` (`optimizer.py:409-410`).

**`dt[]` in the objective:** dt does **not** appear as a direct multiplier on cost terms (prices `p_N`/`p_E` are per-Wh and variables are already Wh, so cost is unit-correct without dt). dt enters the *penalty scaling* once: `self.prc_p_goal_pen = penalty_base * np.max(self.time_series.dt)/3600 * 10e1` (`optimizer.py:89`).

---

## 3. Multi-battery: truly independent SoC trajectories + shared balance?

**VERDICT: CONFIRMED.** N batteries, each with its own `c`,`d`,`s` variable vectors and its own SoC recursion, coupled only through the single per-slot power-balance equation. README shows a 2-battery worked example with independent SoC columns. Construction loops over `enumerate(self.batteries)` everywhere.

Per-battery variable creation (`optimizer.py:126-146`):

```python
self.variables['c'] = {}
for i, bat in enumerate(self.batteries):
    self.variables['c'][i] = [ pulp.LpVariable(f"c_{i}_{t}", ...) for t in self.time_steps ]
# ... identical loops build d[i] and s[i]
self.variables['s'] = {}
for i, bat in enumerate(self.batteries):
    self.variables['s'][i] = [ pulp.LpVariable(f"s_{i}_{t}", lowBound=0, upBound=bat.s_capacity) for t in self.time_steps ]
```

Independent SoC dynamics per battery (`optimizer.py:425-438`):

```python
for i, bat in enumerate(self.batteries):
    if len(self.time_steps) > 0:
        self.problem += (self.variables['s'][i][0]
                         == bat.s_initial
                         + self.eta_c * self.variables['c'][i][0]
                         - (1 / self.eta_d) * self.variables['d'][i][0])
    for t in range(1, self.T):
        self.problem += (self.variables['s'][i][t]
                         == self.variables['s'][i][t - 1]
                         + self.eta_c * self.variables['c'][i][t]
                         - (1 / self.eta_d) * self.variables['d'][i][t])
```

Single shared balance summing all batteries (`optimizer.py:339-368`):

```python
for t in self.time_steps:
    battery_net_discharge = 0
    for i, bat in enumerate(self.batteries):
        battery_net_discharge += (- self.variables['c'][i][t] + self.variables['d'][i][t])
    ...
    self.problem += (battery_net_discharge + self.time_series.ft[t] + e_grid_imp
                     == e_grid_exp + self.time_series.gt[t])
```

Confirmed by `test_cases/016` (2 batteries, c_priority 2 vs 1, different s_initial/s_max) and the README's BAT0/BAT1 output columns. **Multi-battery is genuinely supported, not faked.**

---

## 4. Per-battery fields → constraints vs objective vs penalties

| Field | Role | Where |
|---|---|---|
| `s_min`, `s_max` | **Soft** SoC band via penalty vars (NOT hard bounds) | constraint `optimizer.py:421-422`, penalty in obj `:267` |
| `s_capacity` | **Hard** upper bound on SoC var | `optimizer.py:144` |
| `s_initial` | **Hard** equality seed of SoC chain | `optimizer.py:428-431` |
| `c_min` | Conditional **hard** lower bound (binary-gated: 0 OR ≥c_min) | `optimizer.py:470-475` |
| `c_max`, `d_max` | **Hard** upper bounds on charge/discharge vars | `optimizer.py:128`, `:136` |
| `s_goal[t]` | **Soft** deadline target via slack penalty | constraint `:441-445`, penalty `:273-277` |
| `p_demand[t]` | **Soft** per-slot min charge via slack + binary (two-alt) | constraint `:448-461`, penalty `:279-283` |
| `p_a` | **Objective term** — value of leftover stored energy | `:256` |
| `c_priority` | **Objective tie-breaker** weight (cost-neutral) | `:321-324` |
| `charge_from_grid` | **Hard** lockout vs grid-import direction binary | `:478-480` |
| `discharge_to_grid` | **Hard** lockout vs grid-export direction binary | `:483-485` |

**Key nuances:**

- **`s_min`/`s_max` are SOFT.** They are enforced through penalty variables `s_min_pen`/`s_max_pen`, not as variable bounds. This is deliberate so an out-of-band `s_initial` doesn't make the model infeasible (`optimizer.py:416-422`):
  ```python
  self.problem += (self.variables['s_max_pen'][i][t] >= self.variables['s'][i][t] - bat.s_max)
  self.problem += (self.variables['s_min_pen'][i][t] >= bat.s_min - self.variables['s'][i][t])
  ```
  with the largest penalty weight in the model, `prc_soc_exc_pen = penalty_base * 10e2` (`optimizer.py:90`, applied `:267`).

- **`s_goal[t]` is a soft deadline.** A slack var `s_goal_pen` lets the goal be missed at a cost (`optimizer.py:441-445`):
  ```python
  if bat.s_goal[t] > 0:
      self.problem += (self.variables['s'][i][t] + self.variables['s_goal_pen'][i][t] >= bat.s_goal[t])
  ```
  Penalty weight `prc_e_goal_pen = penalty_base * 10e1` (`:88`). Goal vars only exist where `s_goal[t] > 0` (`:151-156`) — sparse.

- **`p_demand[t]` is a clever two-alternative soft constraint** with a per-slot binary `z_p_demand`. The "demand is satisfied" branch *or* the "battery is already full to s_max" branch must hold (`optimizer.py:448-461`):
  ```python
  p_demand = min(bat.c_max * self.time_series.dt[t] / 3600., bat.p_demand[t])
  # option 1: reach the per-slot demand
  self.problem += (self.variables['c'][i][t] + self.variables['p_demand_pen'][i][t]
                   + self.M * self.variables['z_p_demand'][i][t] >= p_demand)
  # option 2: excused because battery is at s_max
  self.problem += (self.variables['c'][i][t] + self.variables['p_demand_pen'][i][t]
                   + self.M * (1 - self.variables['z_p_demand'][i][t])
                   - (self.batteries[i].s_max - self.variables['s'][i][t]) >= 0.)
  ```
  Its penalty is **time-weighted to favour charging early** (`optimizer.py:279-283`):
  ```python
  objective += - self.prc_p_goal_pen * self.variables['p_demand_pen'][i][t] * (1 + (self.T - t)/self.T)
  ```

- **`p_a` = end-of-horizon energy value** (currency/Wh), NOT availability. Rewards leftover SoC so the optimizer doesn't dump the battery at horizon end (`optimizer.py:254-256`):
  ```python
  for i, bat in enumerate(self.batteries):
      objective += self.variables['s'][i][-1] * bat.p_a
  ```
  (Note: in `solve()`'s *clean* recomputation it's `(s_final - s_initial)*p_a`, `:613-614`.)

- **`c_priority` weights a cost-neutral tie-break only.** It scales a tiny term (`5e-5 * min_import_price`) on both charge and discharge, biased to charge the higher-priority battery earlier (`(self.T - t)` factor) (`optimizer.py:321-324`):
  ```python
  objective += self.variables['c'][i][t] * self.min_import_price * 5e-5 * (self.T - t) * bat.c_priority
  objective += self.variables['d'][i][t] * self.min_import_price * 5e-5 * (self.T - t) * bat.c_priority
  ```
  API caps `c_priority` to 0..2 (`openapi.yaml:266-271`). It does **not** change feasibility or real cost — purely orders otherwise-equivalent solutions.

- **`c_min` binary gating** (charge is 0 OR ≥ c_min): a `z_c` binary exists only when `c_min>0` (`optimizer.py:205-212`, enforced `:470-475`).

---

## 5. Objective function — what is actually optimized

**VERDICT: CONFIRMED.** Single scalar objective, **maximized**. Assembled in `_setup_target_function` (`optimizer.py:222-326`). OpenAPI states it compactly: `Maximize Σt(-nt*pN + et*pE) + Σi(si,T*pai)` (`openapi.yaml:20`).

Real cost/benefit core:
```python
# optimizer.py:234-256
objective -= self.variables['n'][t] * self.time_series.p_N[t]   # import cost (neg)
objective += self.variables['e'][t] * self.time_series.p_E[t]   # export revenue
objective += self.variables['s'][i][-1] * bat.p_a               # residual-SoC value
# + demand-rate peak charge if active (:260-261)
objective += - self.grid.prc_p_exc_imp * self.variables['p_max_imp_exc']
```

Then **penalty layer** (all negative, scaled off `penalty_base = max(max_import_price, 1e-4)`, `:85`):
- SoC band violations `s_min_pen+s_max_pen` × `10e2` (heaviest) — `:265-267`
- Unmet `s_goal` × `10e1` — `:271-277`
- Unmet `p_demand` × `10e1`, time-weighted earlier — `:279-283`
- Grid import-limit overshoot × `10e1` — `:289-291`
- Grid export-limit overshoot × `10e1`, slightly decreasing over time — `:294-297`

Then **strategy layer** (tiny, "cost-neutral" `1e-5`..`5e-5` nudges) — `:300-324` (see §6).

`get_clean_objective_value()` (`optimizer.py:589-622`) recomputes a **penalty-free, strategy-free** economic value for reporting — so the returned `objective_value` is real money, not polluted by penalty weights.

There is **NO battery-degradation/cycling cost term** and **NO explicit peak-demand minimization** beyond the optional grid demand-rate charge (`prc_p_exc_imp`). Degradation modeling is absent.

---

## 6. Strategy enums — values and effect

**VERDICT: CONFIRMED, 3+2 enum values.** From `openapi.yaml:151-168` and the objective code. All are **secondary, cost-neutral nudges** (explicitly: "without impact to actual cost", `optimizer.py:300`). Default `'none'` (`app.py:142-144`).

`charging_strategy` ∈ `{none, charge_before_export, attenuate_grid_peaks}`:
- `charge_before_export` — penalize export, scaled to push it later, so self-charge wins ties (`optimizer.py:303-306`):
  ```python
  objective += - self.variables['e'][t] * self.min_import_price * 2e-5 * (self.T - t)
  ```
- `attenuate_grid_peaks` — reward charging when solar `ft[t]` is high (grid-peak shaving) (`optimizer.py:309-312`):
  ```python
  objective += self.variables['c'][i][t] * self.time_series.ft[t] * self.min_import_price * 1e-6
  ```

`discharging_strategy` ∈ `{none, discharge_before_import}`:
- `discharge_before_import` — penalize grid import, time-weighted, so battery discharge is preferred (`optimizer.py:315-318`):
  ```python
  objective += - self.variables['n'][t] * self.min_import_price * 5e-6 * (self.T - t)
  ```

(Unknown strategy strings silently no-op — no validation beyond the OpenAPI enum, and `app.py` doesn't enforce it.)

---

## 7. Grid model — limits, prices, units, feed-in

**VERDICT: CONFIRMED.** Grid config (`optimizer.py:17-21`):
```python
@dataclass
class GridConfig:
    p_max_imp: float        # max import power, W (optional)
    p_max_exp: float        # max export power, W (optional)
    prc_p_exc_imp: float    # demand-rate price for exceeding import limit
```

- **Import/export are separate non-negative vars** `n[t]` (import Wh) and `e[t]` (export Wh), `optimizer.py:173-174`, mutually exclusive via direction binary `y[t]` and big-M (`:373-375`):
  ```python
  self.problem += self.variables['e'][t] <= self.M * self.variables['y'][t]
  self.problem += self.variables['n'][t] <= self.M * (1 - self.variables['y'][t])
  ```
  Prevents arbitrage (buy-low-export-high) when `p_E > p_N`.

- **Limits are SOFT by default** (overshoot goes to penalty vars `e_imp_lim_exc`/`e_exp_lim_exc`, gated by binaries `z_imp_lim`/`z_exp_lim` so overshoot is only allowed when the regular limit is genuinely hit) — `optimizer.py:378-403`. The result reports `grid_import_limit_exceeded`/`grid_export_limit_hit` flags and per-slot overshoot arrays rather than going infeasible (`:526-538`, `:552-553`). Limits convert W→Wh per slot via `dt[t]/3600` (`:382`, `:399`).

- **Demand-rate mode (NUANCED):** if both `p_max_imp` and `prc_p_exc_imp` are set (`optimizer.py:102-104`), the import limit becomes a **billing threshold**: power above it is allowed but the *peak* overshoot across the horizon is charged once at `prc_p_exc_imp` (`:407-410`, objective `:260-261`). This is a German *Leistungspreis*/demand-charge model EMHASS does not have natively.

- **Units (CONFIRMED throughout):** energy = **Wh** (`gt`,`ft`,`s`,`c`,`d`,`n`,`e`, results), power limits/`c_max`/`d_max`/`p_max_*` = **W**, durations `dt` = **seconds**, prices `p_N`/`p_E`/`p_a` = **currency/Wh**. Confirmed in dataclass comments (`:43-47`), API descriptions (`app.py:62-89`), and OpenAPI (`:170-316`). NOT kW/kWh — sub-unit Wh/W and per-Wh prices (test 016: `p_a ≈ 0.00029` ≈ 0.29 €/kWh).

- **Feed-in:** revenue `+e[t]*p_E[t]` (`:251-252`); per-battery `discharge_to_grid` gate decides if a battery may feed (`:483-485`); `charge_from_grid` gate decides if a battery may pull from grid (`:478-480`). Efficiencies `eta_c`/`eta_d` default 0.95, applied asymmetrically in SoC dynamics (`:430-431`).

---

## What EMHASS must MATCH / can EXCEED

| Dimension | evopt behaviour | EMHASS must MATCH | EMHASS can EXCEED |
|---|---|---|---|
| Slot model | **Variable** per-slot `dt[]` in seconds (e.g. 328s then 3600s) | Accept non-uniform, second-resolution slots incl. a short leading partial slot | EMHASS today assumes fixed `optimization_time_step`; matching variable dt is a real gap to close |
| Multi-battery | True N-battery, independent SoC, one shared balance | Per-battery SoC trajectories + per-battery params in one solve | EMHASS single-battery focus; multi-asset is a gap |
| EV representation | No `Type`; EV = battery with `s_goal[]`/`p_demand[]` + `d_max=0` | Express EV target/deadline as soft per-slot SoC goal and per-slot min-charge with slack | EMHASS deferrable-load model + true plug-in/availability windows are *richer* — evopt can't say "unplugged slots 5-12" |
| Soft constraints | `s_min/s_max`, goals, demand, grid limits all **soft** (penalty+slack) → never infeasible for these | Return a usable schedule + violation flags instead of "Infeasible" | EMHASS can match; good UX pattern to adopt |
| Demand charge | `prc_p_exc_imp` peak-overshoot billing | Optional grid demand-charge (Leistungspreis) term | EMHASS lacks this natively — must ADD |
| Direction lock | Binary `y[t]` blocks simultaneous import+export, per-battery grid-charge/discharge gates | Prevent buy→sell arbitrage; honour charge_from_grid/discharge_to_grid | EMHASS comparable |
| Strategy nudges | 3 charge + 2 discharge cost-neutral tie-breakers + `c_priority` 0..2 | Map evcc strategy enums to equivalent tie-break weights | EMHASS can EXCEED with explicit multi-objective weighting |
| Objective | Maximize: −import +export +residual-SoC value, soft penalties, no degradation, no peak min | Match cost/export/residual-value core; report clean (penalty-free) objective | EMHASS can EXCEED — add **battery degradation/cycle cost** (evopt has none) and thermal/deferrable-load richness |
| Units | Wh / W / seconds / currency-per-Wh | Ingest and emit in Wh & per-Wh (not kWh) | conversion shim needed |

---

## BOTTOM LINE

evopt is a **single PuLP MILP that maximizes economic benefit** over a **variable-width, seconds-resolution horizon**, treating **every asset as a generic battery** — EVs are not a type but a battery carrying a soft per-slot SoC **goal** (`s_goal[]`) and/or per-slot minimum-charge **demand** (`p_demand[]`) with `d_max=0`. **Multi-battery is genuinely supported** (independent SoC chains, one shared power balance, `c_priority` 0..2 as a cost-neutral tie-break). The objective is `−Σ import·p_N + Σ export·p_E + Σ residual_SoC·p_a`, with everything else (SoC band, goals, demand, grid limits) implemented as **soft penalties so the model essentially never returns Infeasible**, plus an optional **peak demand-charge** (`prc_p_exc_imp`). It has **no degradation cost and no real availability windows.**

**The single biggest thing EMHASS must add to be a drop-in for evcc:** accept and solve on a **variable, second-resolution `dt[]` slot grid with N independent batteries in one request, and represent EV deadlines as *soft* per-slot SoC goals + per-slot min-charge demand with slack (returning violation flags rather than Infeasible)** — i.e. the soft-goal / variable-slot / multi-battery contract, since EMHASS today is fixed-step, single-battery, and hard-constraint-infeasible-prone. (Conversely, EMHASS already EXCEEDS evopt on plug-in/availability windows, deferrable loads, and could add battery degradation cost that evopt entirely lacks.)
