# EV charging requirements from the evcc side

**Purpose:** input to multi-battery phase 2 (V2G / intermittently connected battery) in LesIT1's
programme (upstream discussions #610 and #1150), and the specification an EV demand has to
satisfy in the registry sidecar of RFC 0001 (`rfcs/0001-shared-plan-registry.md`,
prototype `prototypes/flexd/`).
**Scope:** what the planner must be able to express and what the executor must be able to
carry out, with the real field each requirement maps to. Not a design for the core model; the
phase 2 formulation is LesIT1's to propose.
**Verified against:** EMHASS release `v0.18.6` (`src/emhass/utils.py`, `treat_runtimeparams`;
`docs/cookbook/ev_evcc_executor.md`); evcc `master` at `daacfa7` (2026-09-29): `api/api.go`,
`api/chargemode.go`, `api/plans.go`, `server/http.go`, `server/http_loadpoint_handler.go`,
`server/openapi.state.yaml`, `core/keys/loadpoint.go`, `core/loadpoint.go`,
`core/loadpoint_api.go`, `core/loadpoint_effective.go`, `core/helper.go`, `core/site.go`.
Anything not verified is listed under
"Open questions" at the end rather than stated as fact.
**Author:** OptimalNothing90
**Date:** 2026-10-17

## How to read this document

Each requirement has a number, a statement, the fields it maps to on each side, and one
acceptance scenario. "Planner" is EMHASS. "Executor" is evcc. "Lifecycle layer" is the sidecar
of RFC 0001. The three roles are fixed by upstream #789: EMHASS recommends and never actuates;
no evcc or Home Assistant coupling code enters the core; the executor and the lifecycle layer
are glue outside it.

Three EMHASS representations of an EV appear below:

- **Today (v0.18.6): windowed deferrable load.** The route the upstream cookbook
  `docs/cookbook/ev_evcc_executor.md` documents and the lifecycle layer uses. Energy target,
  window, nominal power. No state of charge.
- **Phase 2 (proposed in #610, not built):** the EV as one battery in the `number_of_batteries`
  list with a per-timestep connected mask, a re-anchored SOC on reconnection, and a per-battery
  SOC target at departure. Field names for phase 2 are proposals and are marked as such.
- **Phase 1 (shipped, #1032, 0.18.x) used as an interim:** the EV as a stationary battery with
  `soc_init` per battery while connected. Usable only inside one connection window.

Field names in backticks are verified in the sources above. Proposed names carry the word
"proposed".

## A. Scope

### R1. Charge-only is the minimum scope; discharge (V2G) is optional and off by default

The planner must be able to plan an EV that can only take energy. Bidirectional capability is
an opt-in per vehicle, never assumed.

- Executor: evcc loadpoints charge only; no discharge API exists on a loadpoint in the sources
  read. Nothing to map.
- Planner, today: a deferrable load is charge-only by construction.
- Planner, phase 2: the EV battery needs a zero discharge limit by default
  (`battery_discharge_power_max` entry of 0 for that battery, phase 1 list field), and the
  SOC chain must still work with discharge pinned to zero.
- Lifecycle layer: `type: "ev"` demands are charge-only; a `charge_only` flag, if added, must
  default to true.

Acceptance: a vehicle registered with no discharge capability never appears with negative
power in any plan slot, in any mode, including when export prices are higher than import
prices. A bidirectional vehicle appears with negative power only when its registration says
so.

## B. Availability

### R2. Arrival (connection) opens the window

A demand starts when the vehicle is connected, not when the user remembers to register it.
The planner must not schedule charging before the connection instant.

- Executor: `connected` (bool, state key) flips true; `connectedDuration` (seconds) counts
  from it; `vehicleDetectionActive` says the executor is still identifying which vehicle.
- Planner, today: `start_timesteps_of_each_deferrable_load` (slot index, 0 = now).
- Planner, phase 2: the connected mask for that battery becomes true from the arrival slot.
- Lifecycle layer: `window_start` (ISO datetime with offset; defaults to now when absent).

Acceptance: a demand registered with a `window_start` in the future gets zero power in every
slot before it; a demand registered at connection time gets its first eligible slot at the
current step, never earlier. If `vehicleDetectionActive` is true, the registration waits for
identification or uses the loadpoint default vehicle, and the choice is recorded.

### R3. Departure closes the window and carries the target

The planner needs a departure instant per connection, and the energy or SOC the vehicle must
have at that instant.

- Executor, energy-based: `POST /api/loadpoints/{id}/plan/energy/{kWh}/{RFC3339}`
  (`planEnergy` in kWh, `planTime` as RFC 3339); `effectivePlanTime` is the one the executor
  will act on.
- Executor, SOC-based: `POST /api/vehicles/{name}/plan/soc/{percent}/{RFC3339}` (one static
  plan) and `POST /api/vehicles/{name}/plan/repeating` with `RepeatingPlan{weekdays 0 to 6,
  time "HH:MM", tz (IANA), soc, active}`; `effectivePlanSoc` and `effectivePlanId` name the
  plan the executor picked.
- Planner, today: `end_timesteps_of_each_deferrable_load` (slot index, computed in the
  cookbook from the deadline and the step length); the energy target goes through
  `operating_hours_of_each_deferrable_load` at `nominal_power_of_deferrable_loads`.
- Planner, phase 2: a per-battery SOC target at departure (proposed; today only the scalar
  runtime pair `soc_target` plus `soc_target_timestep` exists, naive-MPC only, and #1150 lists
  a per-battery `soc_target` list as a later proposal).
- Lifecycle layer: `deadline` (ISO datetime with offset) and `energy_target_wh`.

Acceptance: with a departure of 07:00 and a target that needs four hours at nominal power, the
plan places exactly four nominal-power slots (or the equivalent energy for a modulating
charger) at or before the slot containing 07:00 and none after it. Moving the departure
earlier by two hours re-plans within one cycle without a re-registration.

### R4. Several availability windows inside one horizon

A vehicle may leave in the morning and return in the afternoon inside a 48-slot horizon. The
planner must be able to plan the second window with the SOC the vehicle will have on return,
not the SOC it has now.

- Executor: repeating plans give the next departure per weekday; nothing in the loadpoint
  state announces a future return. The return time has to come from the consumer (calendar,
  habit, or the user).
- Planner, today: one `start_timesteps` / `end_timesteps` pair per deferrable load. A second
  window is a second deferrable load with its own energy target, and nothing links the two
  through a shared SOC. The cookbook recipe plans one window per connection.
- Planner, phase 2: per-timestep connected list per battery, as scruysberghs proposed in #610
  and LesIT1 adopted for phase 2 (proposed field).
- Lifecycle layer: one window per demand today. A consumer wanting two windows registers two
  demands; the second one's `energy_target_wh` is the consumer's estimate.

Acceptance: a vehicle connected 06:00 to 08:00 and again 17:00 to 23:00 gets a plan whose
energy in the second window is computed from the SOC expected at 17:00 (R5), and the first
window receives only what is needed for the morning trip plus any surplus the price signal
justifies. Under the deferrable-load interim, the per-demand result says the two windows are
unlinked (R16 vocabulary).

### R5. Energy used while away

Between two windows the SOC drops by the trip. The planner needs that drop as an input; the
executor cannot supply it in advance.

- Executor: `vehicleSoc` (percent) on reconnection is the ground truth; `vehicleRange` (km)
  and `vehicleOdometer` (km) are available for a consumer that wants to estimate from distance.
- Planner, phase 2: a re-anchor on reconnection, "a runtime `soc_on_return`, or a
  driving-consumption delta" in LesIT1's words in #610 (proposed).
- Lifecycle layer: not expressible today; the consumer encodes its estimate in the second
  demand's `energy_target_wh`.

Acceptance: a vehicle leaving at 50 % and expected to use 15 % is planned to reach the
evening window at 35 %; when it actually returns at 30 %, the next cycle re-plans from 30 %
without manual intervention and the per-demand result shows the correction.

## C. State of the vehicle

### R6. Current SOC with a timestamp and a staleness rule

Every plan needs the SOC it started from, when that SOC was observed, and what to do when it
is old.

- Executor: `vehicleSoc` (percent, state key). The executor keeps a `socUpdated` instant
  internally (`core/loadpoint.go`), but no state key or API field publishes it in the sources
  read (see open question Q1). SOC polling is configured per loadpoint: `charging` (default),
  `connected`, or `always`, with an interval. `vehicleSoc` may be a charger-estimated value
  when the vehicle has no API.
- Planner, today: SOC is not an input; the consumer converts to energy before calling.
- Planner, phase 1 and 2: `soc_init` as a per-battery list (fraction 0 to 1, not percent;
  values above 1 are rejected since v0.18.x). Phase 2 adds the re-anchor of R5.
- Lifecycle layer: not stored today; the consumer computes `energy_target_wh` from it.
  Requirement: an EV demand carries `soc_percent` and `soc_observed_at`, and a configurable
  `soc_max_age` after which the demand is planned on the last known SOC with reason
  `soc_stale` (proposed field names for the lifecycle layer).

Acceptance: an SOC observed 20 minutes ago under a 30-minute staleness rule is used as is;
one observed 3 hours ago is used but the per-demand result carries `soc_stale`, and the
executor is asked to poll (`connected` poll mode or a one-shot refresh) before the next cycle.
A request that omits the timestamp is rejected, not silently treated as fresh.

### R7. Usable capacity, not nameplate

The energy the planner may put into the vehicle is bounded by the usable capacity between the
current SOC and the applicable upper limit, which is the lowest of the user limit, the vehicle
limit and 100 %.

- Executor: vehicle `Capacity()` (kWh, `api.BatteryCapacity`); `limitSoc` (loadpoint, percent)
  and `vehicleLimitSoc` (vehicle API limit, percent); `effectiveLimitSoc` is the executor's
  resolution; `limitEnergy` (kWh) for vehicles without SOC. Whether the vehicle's capacity is
  exposed in `/api/state` is open question Q2.
- Planner, phase 2: `battery_nominal_energy_capacity` (Wh) and
  `battery_maximum_state_of_charge` (fraction) per battery, phase 1 list fields.
- Lifecycle layer: `energy_target_wh` must already be clipped to
  `capacity_wh × (limit_soc − soc)`; a target above that is rejected with reason
  `exceeds_usable_capacity` (proposed).

Acceptance: a 77 kWh nameplate vehicle at 60 % with a user limit of 80 % yields a target of
at most 15.4 kWh before losses; a request for 20 kWh is reduced to 15.4 kWh and the result
says why.

### R8. Charging losses are explicit

The energy the executor meters on the AC side is larger than the energy that ends up in the
pack. Targets expressed in SOC must be converted with a loss factor; targets expressed in
metered energy must not.

- Executor: `chargedEnergy` and `sessionEnergy` (kWh) are meter-side; `vehicleSoc` is
  pack-side.
- Planner, phase 2: `battery_charge_efficiency` per battery (phase 1 list field). Today's
  deferrable load has no efficiency; the consumer divides by the efficiency before setting
  the energy target.
- Lifecycle layer: `energy_target_wh` is AC-side by definition (it becomes a deferrable
  load's energy). An EV demand carrying SOC fields states `charge_efficiency` (proposed,
  default documented) so the conversion is visible.

Acceptance: a 10 kWh SOC gap with 90 % efficiency is submitted as 11.1 kWh AC-side; the
executor's `chargedEnergy` reaching 11.1 kWh is accepted as "target met" even if the vehicle
reports 79 % rather than 80 %, and the discrepancy is logged with the efficiency used.

### R9. Target SOC per departure

Each departure may have a different target (weekday commute versus weekend trip).

- Executor: repeating plans carry `soc` per weekday set (`RepeatingPlan`), the static plan
  carries one `soc`; `effectivePlanSoc` is the one in force. For vehicles without SOC the
  loadpoint plan carries `planEnergy` instead.
- Planner, phase 2: per-battery SOC target at departure (proposed); interim is the scalar
  `soc_target` and `soc_target_timestep` pair, which binds the whole battery list to one
  value and is therefore unsuitable once more than one battery exists.
- Lifecycle layer: `energy_target_wh` per demand already allows a different target per
  registration.

Acceptance: a vehicle with a repeating plan of 70 % on weekdays and 95 % on Saturday is planned
to 70 % on Thursday night and to 95 % on Friday night, each from the then-current SOC, without
the consumer re-registering anything but the departure.

## D. Power and current

### R10. Minimum and maximum power come from current, phases and voltage

The executor controls current, not power. The planner's power bounds must be derived from the
executor's current bounds and the active phase count, and must be re-derived when either
changes.

- Executor: `minCurrent` and `maxCurrent` (A, loadpoint; defaults 6 A and 16 A in
  `core/loadpoint.go`), set via `POST /api/loadpoints/{id}/mincurrent/{A}` and
  `.../maxcurrent/{A}`, each validated against the other; `effectiveMinCurrent` and
  `effectiveMaxCurrent` fold in the vehicle's and the charger's own limits
  (`core/loadpoint_effective.go`); `phasesActive` (1, 2 or 3). There is no watt setpoint
  (coordination synthesis F14).
- Planner, today: `nominal_power_of_deferrable_loads` (W) and
  `minimum_power_of_deferrable_loads` (W, when the load is continuous rather than
  semi-continuous).
- Planner, phase 2: `battery_charge_power_max` (W) per battery (phase 1 list field).
- Lifecycle layer: `nominal_power_w` and `p_min_w`; `modulating: true` for a charger that
  may run anywhere between the two.

Acceptance: with `effectiveMinCurrent` 6 A, `effectiveMaxCurrent` 16 A and `phasesActive` 3
at the site voltage (`Voltage`, default 230 V in `core/site.go`, used by `currentToPower` in
`core/helper.go`), the planner sees 4.1 kW minimum and 11.0 kW maximum;
when the executor reports `phasesActive` 1, the next cycle plans between 1.4 kW and 3.7 kW.
A plan slot below the minimum is never emitted; the slot is either zero or at least the
minimum.

### R11. Phase switching is a step in power, not a continuum

A 1p/3p-capable charger has a gap between the single-phase maximum and the three-phase
minimum. The planner either plans on a fixed phase count or knows about the gap.

- Executor: `phasesConfigured` (0 = automatic, 1, 3; `POST /api/loadpoints/{id}/phases/{n}`;
  automatic needs a charger implementing `api.PhaseSwitcher`, and the value cannot exceed the
  physically connected phases); `chargerPhases1p3p` says the charger can switch;
  `phasesActive` is what the executor expects to be live.
- Planner, today and phase 2: no notion of phases. The EV is one power range.
- Lifecycle layer: a fixed phase count per demand, or two registrations. Requirement: an EV
  demand states `phases` (1 or 3, proposed) and the lifecycle layer sets
  `phasesConfigured` accordingly before the first slot, or declares `phases_auto` and accepts
  that the executor may land in the gap.

Acceptance: a plan asking for 5 kW on a 1p/3p charger is realised as either 3.7 kW on one
phase or 4.1 kW on three phases, and the per-demand result records which and the reason
`phase_gap` (proposed). A demand registered with `phases: 3` never causes the executor to
switch to one phase while the demand is active.

### R12. Discrete current steps

Most chargers accept whole amperes. The plan's power per slot must be realisable as an integer
current, or the executor will round and the plan will under- or over-deliver.

- Executor: `api.CurrentController.MaxCurrent(current int64)` is the default charger
  interface (whole amperes); `api.ChargerEx.MaxCurrentMillis(float64)` exists for chargers
  with milliampere precision. `chargeCurrents` (A per phase) and `offeredCurrent` (A) report
  what was applied. The 6 A to 32 A range per phase in 1 A steps is the common case; the
  executor itself validates only min ≤ max, not a step size.
- Planner: continuous power inside the bounds. Semi-continuous loads
  (`treat_deferrable_load_as_semi_cont`) are either 0 or nominal, which is realisable by
  construction.
- Lifecycle layer: for a `modulating` EV demand, round the plan's setpoint down to the
  nearest integer current at the active phase count before publishing it, and expose the
  rounding (`setpoint_w` as published versus `plan_w` as solved; proposed).

Acceptance: a planned 5.0 kW slot on three phases becomes 7 A (4.8 kW) and the result shows
both numbers; the shortfall is added to the remaining energy for the next cycle rather than
lost.

### R13. Interruptibility and session behaviour

Stopping and restarting a charge is cheap for most vehicles but some fall asleep and need a
wake-up, and some chargers have a minimum on time.

- Executor: `enabled` and `charging` state keys; the vehicle sleep issue is documented in
  the cookbook (evcc#28652: the executor does not auto-wake); `enableDelay` and
  `disableDelay` (seconds) debounce the executor's own PV logic, not the planner's slots.
- Planner, today: `set_deferrable_load_single_constant` (one contiguous block),
  `def_minimum_on_time` and `def_minimum_off_time`, `set_deferrable_max_startups`,
  `set_deferrable_startup_penalty`; `def_current_state` and `def_current_on_timesteps` carry
  the running state into the next solve.
- Lifecycle layer: `interruptible` (bool, default true; not yet mapped to a runtime parameter
  in the prototype, a documented gap).

Acceptance: a demand with `interruptible: false` produces one contiguous block of slots or is
reported `unschedulable` with that reason; a demand with `interruptible: true` may be split,
and a vehicle that needs a wake-up gets at most the configured number of starts per horizon.

## E. Degraded conditions

### R14. No telemetry

The vehicle has no API, or the API is down. The system must still charge the car sensibly and
must say that it is planning blind.

- Executor: `vehicleSoc` absent or stale; `chargeRemainingEnergy` null; `limitEnergy` and
  `planEnergy` (kWh) are the executor's own SOC-free path; charger-estimated SOC may be
  present for some chargers.
- Planner: unaffected; it plans the energy it is given.
- Lifecycle layer: an EV demand without SOC is registered with an explicit
  `energy_target_wh` and the result carries `soc_unknown` (proposed). The default when the
  consumer gives nothing is a documented fixed energy per session, never "full capacity".

Acceptance: with the vehicle API unreachable, the registration still succeeds with an energy
target, the plan is produced, the result flags `soc_unknown`, and when `vehicleSoc`
reappears the next cycle re-plans from it and clears the flag.

### R15. Late arrival

The vehicle arrives later than the window the consumer registered, so the remaining window is
shorter than the energy needs.

- Executor: `connected` turns true late; `planOverrun` (seconds) says by how much the
  executor's own plan would miss its target.
- Planner, today: `start_timesteps` moves to the arrival slot; if the window cannot hold the
  energy at nominal power the hours are reduced to what fits (lifecycle layer) and the result
  says `truncated`.
- Lifecycle layer: `window_start` updated by refresh; `truncated` reason already implemented.

Acceptance: a demand for 22 kWh with a 07:00 departure, registered at 20:00 but connected at
03:00, is planned for the four remaining hours (44 kWh capacity at 11 kW is enough) and the
same demand connected at 05:30 is planned for 1.5 hours with `truncated` set and the shortfall
stated in Wh.

### R16. Unreachable target never produces an infeasible solve

Whatever the inputs, the planner returns a usable plan for the rest of the house and a clear
statement of what the EV will miss. This is coordination synthesis N5 for the EV path and
acceptance criterion 3 of RFC 0001.

- Executor: `planOverrun` is the executor-side analogue.
- Planner, today: the lifecycle layer pre-shrinks the request (R15) so the solve stays
  feasible; the planner itself has no soft EV target.
- Planner, phase 2: the SOC target at departure must be a soft constraint with a penalty
  (the pattern of the soft `soc_final` penalty in 0.18.x), never an equality.
- Lifecycle layer: reasons `truncated`, `clamped` (deadline beyond the horizon),
  `unschedulable` (window closed or degenerate) and the whole-slot rounding (`timesteps`
  versus requested hours) are emitted today. Required additions for the EV type:
  `soc_stale`, `soc_unknown`, `exceeds_usable_capacity`, `phase_gap`, `shortfall_wh`
  (proposed).

Acceptance: a target of 100 % by a departure 30 minutes away yields a plan where every other
load and the home battery are scheduled normally, the EV gets the one slot it can, and the
result states the shortfall in Wh with a machine-readable reason. `optim_status` for the run
is not `Infeasible`.

## F. Responsibilities

### R17. Split between planner, executor, lifecycle layer and the person

Exactly one party decides each thing.

| Decision | Owner | Field or mechanism |
|---|---|---|
| Which slots the EV charges in, at what power | Planner | `P_deferrable{n}` per slot in `GET /api/v1/plan` (today); `P_batt_{k}` per battery (phase 1 output naming) |
| Translating a slot into charger behaviour | Executor | `POST /api/loadpoints/{id}/mode/{now|off}` for on/off at the configured rate (cookbook step 3); `.../maxcurrent/{A}` for a modulating setpoint; `.../phases/{n}` |
| Holding the current inside charger and vehicle limits, talking to the car | Executor | `effectiveMinCurrent`, `effectiveMaxCurrent`, vehicle API |
| Registration, expiry, ownership, restart, attribution, reasons | Lifecycle layer | RFC 0001 acceptance criteria |
| Overriding the plan | The person, through the executor | any manual change of `mode`, `limitSoc`, `planEnergy`, `planTime`, `smartCostLimit`, `batteryBoost`, `priority` in the executor UI or API |

Rules that follow:

- The planner never calls the executor (#789). The lifecycle layer or the consumer's glue
  does.
- Executor features that plan on their own (`smartCostLimit`: fast charge below a price;
  `batteryBoost`: use the home battery to fast charge; PV-surplus modes `pv` and `minpv`,
  which the current executor normalises to `smart` with an always-charge flag) are off for a
  loadpoint the planner drives, or the plan and the executor fight. The cookbook documents
  the `pv`/`minpv` variant as a deliberate trade-off that forfeits the deadline guarantee.
- A manual override is detected by the lifecycle layer as a divergence between the published
  setpoint and the executor's `mode`, `chargePower` or `charging`, and is reported with
  reason `overridden` (proposed); the demand is not fought, it is marked.
- The executor must not control the home battery when the planner does (cookbook
  prerequisite): the battery is excluded from the executor's meters.

Acceptance: when the person switches the loadpoint to `now` by hand during a planned OFF slot,
the next cycle sees `chargePower` above zero against a zero setpoint, marks the demand
`overridden`, passes the real power as `def_current_power` so the planner schedules around it,
and never sends `mode/off` on top of the person's choice until the demand is refreshed or
withdrawn.

### R18. Feedback of charged energy

Remaining energy for the next cycle must come from what was actually delivered, not only from
what was planned.

- Executor: `chargedEnergy` and `sessionEnergy` (kWh, session), `chargePower` (W, live),
  `chargeRemainingEnergy` (kWh, executor's estimate against its own plan), `vehicleSoc`.
- Planner, today: `def_current_power` (W) pins slot 0 to the live power (cookbook step 5;
  since the release after v0.17.7); `def_current_state` and `def_current_on_timesteps` carry
  the on/off state and elapsed on time.
- Lifecycle layer: accrues from the adopted plan today (plan-slot overlap scaled by power
  ratio); a measured value must take precedence when present. Requirement: refresh accepts
  `delivered_wh` (proposed) and `current_power_w` (exists) from the executor.

Acceptance: a plan expecting 5.5 kWh in a slot during which the executor delivered 4.8 kWh
(R12 rounding, or the car tapering) leaves 0.7 kWh more remaining at the next cycle than the
plan alone would say; a session reset (`connected` false then true) resets the delivered
counter and the lifecycle layer does not credit the old session's energy to the new demand.

## G. Time and units

### R19. Time zone and daylight-saving rules

All three parties agree on instants, not wall-clock strings, and the consumer owns the
conversion from "07:00 tomorrow" to an instant.

- Executor: `planTime` and `effectivePlanTime` are RFC 3339 with offset; `RepeatingPlan.tz`
  is an IANA zone, so "07:00 on weekdays" survives a DST change on the executor's side.
- Planner: `time_zone` is a configuration parameter; the cookbook warns that
  `delta_forecast_daily` uses local calendar-day semantics and that the deadline arithmetic
  done in a Home Assistant template is separate from it. Slot indices are relative to the
  first step of the current run.
- Lifecycle layer: every datetime must be timezone-aware (naive datetimes are rejected),
  stored as UTC, and the step grid is aligned to the planner's own rounding of the first
  step; the deployment's UTC offset must be a multiple of the step (30 min steps fit every
  whole- and half-hour zone).

Acceptance: a repeating departure of 07:00 Monday to Friday is planned to the same local
07:00 on the Sunday-to-Monday night of a DST change (a 23- or 25-hour day), and the deadline
slot index the lifecycle layer computes equals the slot the planner labels with that local
07:00 in `GET /api/v1/plan`. A naive datetime in a registration is rejected with a 4xx.

### R20. Units

Conversions happen once, at the lifecycle layer, and are documented in the response.

| Quantity | evcc | EMHASS | Lifecycle layer |
|---|---|---|---|
| Energy | kWh (`planEnergy`, `chargedEnergy`, `sessionEnergy`, `chargeRemainingEnergy`, `limitEnergy`) | Wh (`battery_nominal_energy_capacity`); hours × W for deferrables (`operating_hours_of_each_deferrable_load`) | Wh (`energy_target_wh`) |
| Power | W (`chargePower`) | W (`nominal_power_of_deferrable_loads`, `battery_charge_power_max`, `def_current_power`) | W (`nominal_power_w`, `p_min_w`, `current_power_w`, setpoints) |
| Current | A, per phase (`minCurrent`, `maxCurrent`, `chargeCurrents`) | none | none (derived from W at the active phase count and the site `Voltage`) |
| State of charge | percent, integer in APIs (`vehicleSoc`, `limitSoc`, plan `soc`) | fraction 0 to 1 (`soc_init`, `soc_final`, `soc_target`, `battery_*_state_of_charge`) | percent in proposed fields; converted to fraction when passed on |
| Time | RFC 3339 with offset; seconds for durations (`planOverrun`, `chargeDuration`) | slot indices relative to the run start; `optimization_time_step` in minutes | ISO datetimes with offset, UTC internally |
| Phases | 0/1/3 configured, 1/2/3 active | none | 1 or 3 (proposed) |

Acceptance: a registration of 11 kWh for an 11 kW charger produces
`operating_hours_of_each_deferrable_load` of 1.0 h (or 2 timesteps of 30 min for a
semi-continuous load); a `soc_init` of 0.6 is sent for a `vehicleSoc` of 60; the response
echoes the derived values so a reviewer can check the arithmetic without reading code.

## Mapping summary

| Requirement | evcc (verified) | EMHASS v0.18.6 (verified) | Phase 2 (proposed in #610 / #1150) | Lifecycle layer |
|---|---|---|---|---|
| R1 charge-only | no loadpoint discharge API | deferrable load | `battery_discharge_power_max` = 0 | `type: ev` |
| R2 arrival | `connected`, `connectedDuration` | `start_timesteps_of_each_deferrable_load` | connected mask true | `window_start` |
| R3 departure, target | `planEnergy`/`planTime`, vehicle `plan/soc`, `RepeatingPlan` | `end_timesteps_of_each_deferrable_load`, hours × nominal | SOC target at departure per battery | `deadline`, `energy_target_wh` |
| R4 several windows | repeating plans (departures only) | one window per load | per-timestep connected list | one window per demand |
| R5 energy while away | `vehicleSoc` on return, `vehicleRange` | none | `soc_on_return` or driving delta | consumer estimate |
| R6 SOC, timestamp, staleness | `vehicleSoc`; no published timestamp (Q1); poll modes | none (consumer converts) | `soc_init` list, re-anchor | `soc_percent`, `soc_observed_at`, `soc_stale` (proposed) |
| R7 usable capacity | `Capacity()` kWh (Q2), `limitSoc`, `vehicleLimitSoc`, `effectiveLimitSoc`, `limitEnergy` | none | `battery_nominal_energy_capacity`, `battery_maximum_state_of_charge` | clip, `exceeds_usable_capacity` |
| R8 losses | `chargedEnergy` meter-side vs `vehicleSoc` | none | `battery_charge_efficiency` | `charge_efficiency` (proposed) |
| R9 target per departure | `RepeatingPlan.soc`, `effectivePlanSoc` | `soc_target` + `soc_target_timestep` (scalar) | per-battery target list | per-demand target |
| R10 min/max power | `minCurrent`, `maxCurrent`, `effectiveMin/MaxCurrent`, `phasesActive` | `nominal_power_of_deferrable_loads`, `minimum_power_of_deferrable_loads` | `battery_charge_power_max` | `nominal_power_w`, `p_min_w`, `modulating` |
| R11 phase switching | `phasesConfigured`, `chargerPhases1p3p`, `phasesActive` | none | none | `phases` (proposed), `phase_gap` |
| R12 current steps | `MaxCurrent(int64)` vs `MaxCurrentMillis`, `chargeCurrents`, `offeredCurrent` | semi-continuous or continuous | continuous | round down, expose both |
| R13 interruptibility | `enabled`, `charging`, wake issue | `set_deferrable_load_single_constant`, `def_minimum_on_time`, `set_deferrable_max_startups`, `def_current_state` | none | `interruptible` (unmapped today) |
| R14 no telemetry | `limitEnergy`, `planEnergy`, null `chargeRemainingEnergy` | energy-based plan | SOC optional | `soc_unknown` |
| R15 late arrival | `connected`, `planOverrun` | `start_timesteps` moves | connected mask | `truncated` |
| R16 never infeasible | `planOverrun` | lifecycle layer pre-shrinks | soft SOC target with penalty | reason vocabulary |
| R17 responsibilities | `mode`, `maxcurrent`, `phases`; `smartCostLimit`, `batteryBoost` off | `P_deferrable{n}`, `def_current_power` | `P_batt_{k}` | `overridden` (proposed) |
| R18 feedback | `chargedEnergy`, `sessionEnergy`, `chargePower` | `def_current_power`, `def_current_state` | measured SOC re-anchor | `delivered_wh` (proposed) |
| R19 time zones | RFC 3339, `RepeatingPlan.tz` | `time_zone`, slot indices | same | tz-aware, UTC internal |
| R20 units | kWh, W, A, percent | Wh, W, fraction, slots | same as phase 1 | Wh, W, percent in, fraction out |

## Open questions

Items I could not verify in the sources listed at the top. None is assumed true anywhere
above.

- **Q1. SOC observation time.** evcc keeps `socUpdated` in `core/loadpoint.go` but I found no
  state key or REST field that publishes it. Whether the websocket or MQTT publication
  carries a timestamp per value, or whether the executor's Home Assistant integration adds
  one, is not verified. Until it is, R6 makes the consumer stamp the SOC at read time.
- **Q2. Vehicle capacity in the state API.** `api.BatteryCapacity.Capacity()` exists on the
  vehicle; the `capacity` field I found in `openapi.state.yaml` sits in a battery schema
  ("weighted by capacity across all batteries"), and I did not confirm a per-vehicle
  `capacity` in `/api/state`. R7 may need the consumer to configure capacity by hand.
- **Q3. Semantics of `smart` mode.** `api.ChargeModeString` accepts `off`, `now`, `smart`,
  `minpv` and `pv`, and `SetMode` normalises `pv`/`minpv` to `smart` with an always-charge
  flag. I did not trace what `smart` does when a loadpoint plan and a smart-cost limit are
  both set, so R17 lists all three PV-oriented modes as "off when the planner drives".
- **Q4. Per-phase current limit versus total.** `maxCurrent` is documented per phase. Whether
  a 1p/3p charger's current limit applies before or after the executor's phase decision, and
  how `phasesActive` of 2 arises, is not verified beyond the key comment.
- **Q5. Phase 2 field names.** Everything marked "proposed" for phase 2 (connected mask,
  `soc_on_return`, per-battery SOC target at departure, soft target penalty) is taken from
  LesIT1's and scruysberghs's wording in #610 and #1150, not from code. The names are
  placeholders for this document.
- **Q6. `def_current_power` versus the window end.** The flexd acceptance work observed that
  the planner extends the first slot's window when `def_current_power` is above zero; the
  precedence between a running load and a window that has already ended is not documented
  and needs checking in `optimization.py` at v0.18.6 before R17's override behaviour is
  relied on.
- **Q7. Energy-plan execution in `now` mode.** Whether the executor honours `planEnergy` and
  `planTime` while the loadpoint is in `now` mode, or only in `smart`, decides whether R3's
  energy-based plan can coexist with the cookbook's `now`/`off` mapping. Not traced.
- **Q8. Executor-side feedback transport.** The cookbook reads executor state through the
  Home Assistant integration's sensors with placeholder names. Which of `chargedEnergy`,
  `sessionEnergy` and `vehicleSoc` that integration exposes, and under which entity ids, is
  outside the sources read; R18 names the executor's own keys instead.
