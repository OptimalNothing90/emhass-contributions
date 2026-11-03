# EV charging requirements from the evcc side

**Purpose:** the modelling contract for multi-battery phase 2 (V2G / intermittently connected
battery) in LesIT1's programme (upstream discussions #610 and #1150): what the planner has to be
able to express about an EV, with the real evcc field each requirement maps to. It is also the
specification an EV demand has to satisfy in the registry sidecar of RFC 0001
(`rfcs/0001-shared-plan-registry.md`, prototype `prototypes/flexd/`).
**Scope:** planner-side modelling. Executor behaviour (phase switching, current steps, wake-ups,
override detection, transport and reason vocabulary) is not in this document any more; it moved
to RFC 0001, see the changelog and the stubs R11 to R13. Not a design for the core model; the
phase 2 formulation is LesIT1's to propose.
**Verified against:** EMHASS release `v0.18.6` (`src/emhass/utils.py`, `treat_runtimeparams`;
`src/emhass/optimization.py`; `docs/cookbook/ev_evcc_executor.md`); evcc `master` at `daacfa7`
(2026-09-29): `api/api.go`, `api/chargemode.go`, `api/plans.go`, `server/http.go`,
`server/http_loadpoint_handler.go`, `server/openapi.state.yaml`, `core/keys/loadpoint.go`,
`core/loadpoint.go`, `core/loadpoint_api.go`, `core/loadpoint_effective.go`, `core/helper.go`,
`core/site.go`. Additions of the 2026-11-04 revision were read on evcc `master` at `12ce81c`
(2026-11-03) or taken from LesIT1's check against the evcc `0.315.2` tag. The table "evcc
versions per field" below says which. Anything not verified is listed under "Open questions" at
the end rather than stated as fact.
**Author:** OptimalNothing90
**Date:** 2026-10-17 · **Revised:** 2026-11-04

## Changelog

- **2026-11-04.** Revision after LesIT1's review in
  [OptimalNothing90/emhass-contributions#1](https://github.com/OptimalNothing90/emhass-contributions/issues/1)
  (comment of 2026-10-19) and the point-by-point reply of 2026-11-03. The document is now the
  modelling contract; executor concerns moved out. Numbering is stable: no R-number was reused,
  withdrawn ones stay as stubs so reports that cite them still resolve.
  - **New:** R21 (tiers: target, optional deadline, grid eligibility; "open-ended, no departure"
    as a first-class tier), R22 (shared site import cap).
  - **Folded into R21:** R3 (departure target) and R9 (target per departure).
  - **Moved to RFC 0001** (section "Executor concerns moved from ev-requirements.md"): R11 phase
    switching, R12 current steps, R13 interruptibility and wakes; override detection (was in
    R17); transport and reason vocabulary (was in R6, R7, R14, R15, R16, R18).
  - **Changed:** "Phase 1 as an interim" now says it cannot run next to a house battery that uses
    `soc_target`; R6 staleness per source, no single default; R7 `limitSoc` 0 is unset; R10
    minimum charge power is a modelling requirement; R17 evcc plans are inputs only, new
    `minSoc` line; R20 `vehicleSoc` is a float; R18 delivered energy feeds back because a
    circuit can trim below plan.
  - **Added:** column for evcc `0.315.2` next to `master` for the mode vocabulary, per-field
    version table, evidence that evcc's own optimizer knows `charge_from_grid` only as yes/no,
    LesIT1's answers to Q1, Q3, Q4, Q7, Q8 (marked as one installation, evcc 0.315.2).
  - **Closed or corrected:** Q2 closed (`vehicles.<name>.capacity`), Q5 attribution corrected,
    R11 example corrected to 3.9 kW, R13 reworded, Q9 added.
- **2026-10-17.** First version.

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
  `soc_init` per battery while connected. Usable only inside one connection window, and **not
  usable next to a house battery that itself uses the runtime `soc_target`**: at v0.18.6 the
  runtime `soc_target` is one scalar, and the optimiser applies the identical fraction as a
  floor to every battery, each clamped to its own `soc_max`
  (`src/emhass/optimization.py`, comment at line 6959, tagged #610). A `soc_target` of 1.0 sent
  for the house battery in the afternoon would therefore also put a floor under the EV battery,
  and any value sent for the EV would bind the house battery. The collision disappears only
  with a per-battery target (#1150 lists it as a later proposal).

Field names in backticks are verified in the sources above. Proposed names carry the word
"proposed".

### evcc versions per field

Two evcc releases matter. `0.315.2` is what the one installation that reviewed this document
runs (LesIT1); `master` is what I read. A field not listed here was checked on `master` at
`daacfa7` only and is not confirmed on `0.315.2`. "LesIT1" in the last column means one
installation checked it on the tag; I did not re-read the tag.

| Field or behaviour | 0.315.2 | master | Checked by |
|---|---|---|---|
| `vehicles.<name>.capacity` ("Usable battery capacity in kWh", `Vehicle` schema in `openapi.state.yaml`) | present | present (`12ce81c`) | LesIT1 on 0.315.2; me on master |
| `vehicleSoc` type | number | number (`12ce81c`; was "integer" in the first version of this document) | me on master; LesIT1 for 0.315.2 |
| `limitSoc` | 0 means "no limit"; set to 0 on vehicle disconnect | not re-checked | LesIT1 on 0.315.2 |
| `vehicleSoc` of 0 | treated as unknown by the consumer | not re-checked | LesIT1's practice on 0.315.2 |
| SOC observation timestamp published | none | none found (Q1) | LesIT1 on 0.315.2; me on master |
| `POST /api/vehicles/{name}/minsoc/{n}`, `effectiveMinSoc` (higher of vehicle and loadpoint value) | present | not re-checked | LesIT1 on 0.315.2 |
| `effectivePlanTime`, `effectivePlanSoc`, `effectivePlanId`, `planEnergy`, `planTime`, `RepeatingPlan` | not checked | present (`daacfa7`) | me on master |
| Vehicle wake-up timer (`wakeupTimeout` 30 s, `wakeupAttempts` 6 in `core/timer.go`) | not checked | present (`12ce81c`) | me on master |
| `POST /api/loadpoints/{id}/mode/{now\|off}` | `now`, `off` present | present | LesIT1 uses `now` on 0.315.2; me on master |

### Mode vocabulary

The mode names differ between releases, so the requirements below do not depend on a mode
other than `now` and `off`, which both columns have.

| Mode | evcc 0.315.2 (LesIT1) | evcc master `daacfa7` (me) | evcc 0.318.0 |
|---|---|---|---|
| `off` | yes | yes (`api.ChargeModeString`) | not traced |
| `now` | yes | yes | not traced |
| `minpv` | separate mode | accepted, `SetMode` normalises it to `smart` with an always-charge flag | not traced |
| `pv` | separate mode | accepted, normalised to `smart` | not traced; at automatic level `full` the optimizer also steers `pv` and `minpv` loadpoints |
| `smart` | does not exist | exists | not traced |
| Automatic mode (evcc PR #32881, merged 2026-10-11, release 0.318.0 of 2026-10-24) | does not exist | does not exist | A setting with three levels in the 0.318.0 code (`core/site.go`): `off` (default), `battery` (home battery only) and `full` (home battery and loadpoints); it also needs the experimental and optimizer settings and an authorised sponsor token. At `full`, a loadpoint in `pv`/`minpv` follows the forecast surplus where the plan matches it. Otherwise the optimizer's suggested power sets the charge: full power, a limited current, or minimum charging (`core/loadpoint_optimizer.go`, `optimizerCharging`), so current selection is no longer left to the pv loop. The PR text said "a switch, off by default"; the code is what was read for this row. The `smart` enum on 0.318.0 was not traced. |

If a statement here depends on the mode name, it says which column it is true for. A deployment
below 0.318 has no automatic mode; a deployment at 0.318 or later must keep it at `off` for any
loadpoint and any home battery the planner drives (R17).

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

Acceptance: a vehicle registered with no discharge capability never returns energy in any plan
slot, in any mode, including when export prices are higher than import prices. The sign
depends on the representation: a deferrable load's `P_deferrable{n}` is never negative; a
battery's `P_batt_{k}` is negative while charging and positive while discharging
(`src/emhass/optimization.py`, `p_sto_neg` is non-positive), so for the phase 2 EV battery
"never discharges" means `P_batt_{k}` is never positive. A bidirectional vehicle discharges
only when its registration says so.

## B. Availability

R2, R4 and R15 describe one mechanism from the optimiser's side: a per-timestep connected mask
for the EV battery (as LesIT1 puts it in #1: "R2, R4 and R15 collapse into it"). They stay
separate here because they have different executor sources and different acceptance scenarios.

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

### R3. Moved into R21 (tiers)

Withdrawn as a separate requirement. The departure instant and the target at departure are now
the optional deadline and the target of a tier (R21). The evcc plan endpoints it listed are not
used for writing any more (R17).

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
unlinked.

### R5. Energy used while away

Between two windows the SOC drops by the trip. The planner needs that drop as an input; the
executor cannot supply it in advance.

- Executor: `vehicleSoc` (percent, float, state key) on reconnection is the ground truth;
  `vehicleRange` (km) and `vehicleOdometer` (km) are available for a consumer that wants to
  estimate from distance. A `vehicleSoc` of 0 is unknown, not empty (R6).
- Planner, phase 2: a re-anchor on reconnection, "a runtime `soc_on_return`, or a
  driving-consumption delta" in LesIT1's words in #610 (proposed). LesIT1 notes in #1 that
  re-anchoring touches the terminal-SOC equality and needs its own design round.
- Lifecycle layer: not expressible today; the consumer encodes its estimate in the second
  demand's `energy_target_wh`.

Acceptance: a vehicle leaving at 50 % and expected to use 15 % is planned to reach the
evening window at 35 %; when it actually returns at 30 %, the next cycle re-plans from 30 %
without manual intervention and the per-demand result shows the correction.

## C. State of the vehicle

### R6. Current SOC with an observation time and a staleness rule per source

Every plan needs the SOC it started from, when that SOC was observed, and what to do when it
is old. "Old" is a property of the source, so there is no single default age.

- Executor: `vehicleSoc` (percent, float, state key). The executor keeps a `socUpdated` instant
  internally (`core/loadpoint.go`), but no state key or API field publishes it in the sources
  read; on evcc 0.315.2 there is none either (Q1). SOC polling is configured per loadpoint:
  `charging` (default), `connected`, or `always`, with an interval. There is no route to force
  a SOC read. `vehicleSoc` may be a charger-estimated value when the vehicle has no API. A
  value of 0 is unknown, not a charge level.
- Why no single default, measured on one installation (LesIT1, evcc 0.315.2, cloud vehicle
  API, car at home): the worst gap between SOC updates was 26 minutes. A cloud API can also be
  billed per wake, so a forced read is not a free fix. Home Assistant's `last_reported` on the
  SOC entity stalls for long stretches during a steady charge (about an hour seen), so it is
  not a freshness signal either. A staleness limit of 30 minutes would have flagged healthy
  charges there.
- Consequence for the stamp: a consumer that stamps the SOC "at read time" learns when it
  fetched the value from the executor, not when the vehicle reported it. That detects a dead
  executor, not a stale cloud API. The observation time must come from the source that knows
  it, and where no source publishes one, the age limit for that source has to absorb the
  polling gap (so it is configured above the measured worst gap for that source).
- Planner, today: SOC is not an input; the consumer converts to energy before calling.
- Planner, phase 1 and 2: `soc_init` as a per-battery list (fraction 0 to 1, not percent;
  values above 1 are rejected since v0.18.x). Phase 2 adds the re-anchor of R5.
- Lifecycle layer: not stored today; the consumer computes `energy_target_wh` from it.
  Requirement: an EV demand carries `soc_percent`, an observation time, and names its SOC
  source; the maximum age is configured per source (proposed field names). The flag raised on
  an over-age SOC is in RFC 0001.

Acceptance: two sources are configured with different maximum ages, and the same SOC age is
accepted on one and flagged on the other, from configuration alone. A source whose measured
update gap is 26 minutes and whose configured maximum age is above that does not flag a
healthy charge. A request that omits the observation time or the source is rejected, not
silently treated as fresh. No staleness handling forces a vehicle read unless the consumer
opted in for that source.

### R7. Usable capacity, not nameplate

The energy the planner may put into the vehicle is bounded by the usable capacity between the
current SOC and the applicable upper limit. The consumer takes the lowest of the user limit,
the vehicle's API limit and 100 %, where a limit of 0 is unset. The executor does not do this
for it (see `effectiveLimitSoc` below).

- Executor: `vehicles.<name>.capacity` (kWh, "Usable battery capacity in kWh", `Vehicle`
  schema in `openapi.state.yaml`; vehicle `Capacity()` internally); `limitSoc` (loadpoint,
  percent) and `vehicleLimitSoc` (vehicle API limit, percent); `effectiveLimitSoc` is the
  loadpoint `limitSoc` if above 0, else the per-vehicle limit setting if above 0, else 100.
  It does not look at `vehicleLimitSoc`: the source carries the comment "TODO take vehicle
  api limits into account" on both 0.315.2 and 0.318.0 (`core/loadpoint_effective.go`).
  `limitEnergy` (kWh) for vehicles without SOC. On evcc 0.315.2
  `limitSoc` is 0 for "no limit" and evcc sets it to 0 when the vehicle disconnects, so a 0
  has to be dropped from the minimum, not taken as the smallest limit.
- Planner, phase 2: `battery_nominal_energy_capacity` (Wh) and
  `battery_maximum_state_of_charge` (fraction) per battery, phase 1 list fields.
- Lifecycle layer: `energy_target_wh` must already be clipped to
  `capacity_wh × (limit_soc − soc)`; a target above that is rejected or reduced with a
  machine-readable reason (name in RFC 0001).

Acceptance: a 77 kWh nameplate vehicle at 60 % with a user limit of 80 % yields a target of
at most 15.4 kWh before losses; a request for 20 kWh is reduced to 15.4 kWh and the result
says why. The same vehicle with `limitSoc` 0 and `vehicleLimitSoc` 90 is bounded by 90 %, not
by 0 %.

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

### R9. Moved into R21 (tiers)

Withdrawn as a separate requirement. A different target per departure (weekday commute versus
weekend trip) is a different tier target with its own optional deadline (R21). The scalar
`soc_target` / `soc_target_timestep` pair stays unsuitable once more than one battery exists,
as the "Phase 1 as an interim" bullet now says.

## D. Power and current

### R10. Minimum and maximum charge power, with "off or at least p_min"

The planner must be able to say that in every slot the EV charges either zero or at least a
minimum power, and at most a maximum. The executor controls current; the bounds in watts are
derived from its current bounds, the active phase count and the site voltage.

- Executor: `minCurrent` and `maxCurrent` (A, loadpoint; defaults 6 A and 16 A in
  `core/loadpoint.go`), set via `POST /api/loadpoints/{id}/mincurrent/{A}` and
  `.../maxcurrent/{A}`, each validated against the other; `effectiveMinCurrent` and
  `effectiveMaxCurrent` fold in the vehicle's and the charger's own limits
  (`core/loadpoint_effective.go`); `phasesActive` (1, 2 or 3). There is no watt setpoint
  (coordination synthesis F14).
- Planner, today: `nominal_power_of_deferrable_loads` (W) and
  `minimum_power_of_deferrable_loads` (W, when the load is continuous rather than
  semi-continuous).
- Planner, phase 2: `battery_charge_power_max` (W) per battery (phase 1 list field) gives the
  maximum only. **v0.18.6 batteries have no minimum charge power**, so "off, or at least
  p_min" cannot be modelled with `battery_charge_power_max` alone. The phase 2 EV battery
  needs a semi-continuous charge variable (zero, or between p_min and p_max), the same idea as
  the semi-continuous deferrables (`treat_deferrable_load_as_semi_cont`). This is a model
  requirement, not an executor detail: without it the plan contains slots the charger cannot
  carry out.
- Lifecycle layer: `nominal_power_w` and `p_min_w`; `modulating: true` for a charger that
  may run anywhere between the two.

Acceptance: with `effectiveMinCurrent` 5 A, `effectiveMaxCurrent` 16 A and `phasesActive` 3
at 230 V (`Voltage`, default 230 V in `core/site.go`, used by `currentToPower` in
`core/helper.go` at `daacfa7`; on 0.318.0 the constant and `CurrentToPower` / `PowerToCurrent`
live in `util/grid/grid.go`, which also applies a factor of √3 instead of 3 for a three-wire
grid without neutral), the planner sees p_min about 3.45 kW (the floor on LesIT1's charger) and
p_max 11.0 kW. A plan slot between zero and p_min is never emitted; every slot is either zero
or at least p_min. Re-deriving the bounds when the executor changes the phase count is an
executor concern (RFC 0001).

### R11. Moved to RFC 0001 (phase switching)

Not a modelling requirement. See "Executor concerns moved from ev-requirements.md" in
`rfcs/0001-shared-plan-registry.md`. The corrected acceptance example (3.9 kW, not 5 kW, lies
in the gap) is kept there.

### R12. Moved to RFC 0001 (discrete current steps)

Not a modelling requirement. See the same section of RFC 0001.

### R13. Moved to RFC 0001 (interruptibility, session behaviour, wakes)

Not a modelling requirement. See the same section of RFC 0001, which also carries the
corrected statement about the vehicle wake-up timer.

## E. Degraded conditions

### R14. No telemetry

The vehicle has no API, or the API is down. The system must still charge the car sensibly and
must say that it is planning blind.

- Executor: `vehicleSoc` absent, 0 (unknown) or stale per R6; `chargeRemainingEnergy` null;
  `limitEnergy` and `planEnergy` (kWh) are the executor's own SOC-free path; charger-estimated
  SOC may be present for some chargers.
- Planner: unaffected; it plans the energy it is given.
- Lifecycle layer: an EV demand without SOC is registered with an explicit
  `energy_target_wh` and the result flags that the SOC is unknown (flag name in RFC 0001).
  The default when the consumer gives nothing is a documented fixed energy per session, never
  "full capacity".

Acceptance: with the vehicle API unreachable, the registration still succeeds with an energy
target, the plan is produced, the result flags the unknown SOC, and when `vehicleSoc`
reappears with a non-zero value the next cycle re-plans from it and clears the flag.

### R15. Late arrival

The vehicle arrives later than the window the consumer registered, so the remaining window is
shorter than the energy needs.

- Executor: `connected` turns true late; `planOverrun` (seconds) says by how much the
  executor's own plan would miss its target.
- Planner, today: `start_timesteps` moves to the arrival slot; if the window cannot hold the
  energy at nominal power the hours are reduced to what fits (lifecycle layer) and the result
  says the request was truncated.
- Lifecycle layer: `window_start` updated by refresh.

Acceptance: a demand for 22 kWh with a 07:00 departure, registered at 20:00 but connected at
03:00, is planned for the four remaining hours (44 kWh capacity at 11 kW is enough) and the
same demand connected at 05:30 is planned for 1.5 hours with the truncation flagged and the
shortfall stated in Wh.

### R16. Unreachable target never produces an infeasible solve

Whatever the inputs, the planner returns a usable plan for the rest of the house and a clear
statement of what the EV will miss. This is coordination synthesis N5 for the EV path and
acceptance criterion 3 of RFC 0001.

- Executor: `planOverrun` is the executor-side analogue.
- Planner, today: the lifecycle layer pre-shrinks the request (R15) so the solve stays
  feasible; the planner itself has no soft EV target.
- Planner, phase 2: the tier target (R21) must be a soft constraint with a penalty (the
  pattern of the soft `soc_final` penalty in 0.18.x), never an equality. This is **my
  proposal**, not LesIT1's (Q5).
- Lifecycle layer: reductions carry a machine-readable reason and a shortfall in Wh; the
  vocabulary is in RFC 0001.

Acceptance: a target of 100 % by a departure 30 minutes away yields a plan where every other
load and the home battery are scheduled normally, the EV gets the one slot it can, and the
result states the shortfall in Wh with a machine-readable reason. `optim_status` for the run
is not `Infeasible`.

## F. Responsibilities

### R17. Split between planner, executor, lifecycle layer and the person

| Decision | Owner | Field or mechanism |
|---|---|---|
| Which slots the EV charges in, at what power | Planner | `P_deferrable{n}` per slot in `GET /api/v1/plan` (today); `P_batt_{k}` per battery (phase 1 output naming) |
| Translating a slot into charger behaviour | Executor | `POST /api/loadpoints/{id}/mode/{now\|off}` for on/off at the configured rate (cookbook step 3); `.../maxcurrent/{A}` for a modulating setpoint |
| A minimum SOC the vehicle must hold | Executor, on the planner's behalf | vehicle `minSoc`, `POST /api/vehicles/{name}/minsoc/{n}`; `effectiveMinSoc` is the higher of the vehicle and loadpoint value (0.315.2, LesIT1) |
| Holding the current inside charger and vehicle limits, talking to the car | Executor | `effectiveMinCurrent`, `effectiveMaxCurrent`, vehicle API |
| Registration, expiry, ownership, restart, attribution, reasons | Lifecycle layer | RFC 0001 acceptance criteria |
| Overriding the plan | The person, through the executor | any manual change of `mode`, `limitSoc`, `smartCostLimit`, `batteryBoost`, `priority`, or of evcc's own plan in the executor UI or API |

Rules that follow:

- The planner never calls the executor (#789). The lifecycle layer or the consumer's glue
  does.
- **evcc plans are inputs, never written.** `effectivePlanTime`, `effectivePlanSoc` and
  `effectivePlanId` (and `planEnergy` / `planTime` for vehicles without SOC) tell the consumer
  what the person asked evcc for; they may seed a tier (R21). The consumer does not write
  `plan/energy`, `plan/soc` or `plan/repeating`: evcc would schedule its own slots from them
  and compete with the planner. Where the executor must hold a floor, `minSoc` does that
  (line above), not a plan. (LesIT1 executes the floor with `pv` plus vehicle `minSoc` on
  0.315.2 and does not use evcc plans.)
- Executor features that plan on their own (`smartCostLimit`: fast charge below a price;
  `batteryBoost`: use the home battery to fast charge; the PV-surplus modes `pv` and `minpv`,
  see the mode table) are off for a loadpoint the planner drives, or the plan and the
  executor fight. The cookbook documents the `pv`/`minpv` variant as a deliberate trade-off
  that forfeits the deadline guarantee. From evcc 0.318 the optimizer's automatic mode
  (#32881) acts on the home battery at level `battery` and on `pv`/`minpv` loadpoints too at
  level `full`; it must be `off` while the planner drives the home battery or a loadpoint.
- The executor must not control the home battery when the planner does (cookbook
  prerequisite): the battery is excluded from the executor's meters.
- Detecting that the person overrode a planned slot is an executor and lifecycle concern, in
  RFC 0001.

Acceptance: with a loadpoint the planner drives, no plan endpoint of the executor is written by
the glue (a request log shows none); a floor SOC reaches the executor only through `minsoc`.

### R18. Feedback of charged energy

Remaining energy for the next cycle must come from what was actually delivered, not only from
what was planned. This matters more with the shared cap (R22): an evcc circuit or a phase
limit can trim the EV's current below the plan without anyone deciding to.

- Executor: `chargedEnergy` and `sessionEnergy` (kWh, session), `chargePower` (W, live),
  `chargeRemainingEnergy` (kWh, executor's estimate against its own plan), `vehicleSoc`.
- Planner, today: `def_current_power` (W) pins slot 0 to the live power for a continuous load
  (cookbook step 5; since the release after v0.17.7). A semi-continuous load is not pinned:
  a positive value forces it on at nominal power at slot 0. Single-constant, sequence and
  thermal loads are excluded (`src/emhass/optimization.py`, around line 1217; use
  `def_current_state` for those). `def_current_state` and `def_current_on_timesteps` carry
  the on/off state and elapsed on time.
- Lifecycle layer: accrues from the adopted plan today (plan-slot overlap scaled by power
  ratio); a measured value must take precedence when present. Requirement: refresh accepts a
  measured delivered energy and `current_power_w` (exists) from the executor (field names in
  RFC 0001).

Acceptance: a plan expecting 5.5 kWh in a slot during which the executor delivered 4.8 kWh
(a circuit trimmed the current, or the car tapered) leaves 0.7 kWh more remaining at the next
cycle than the plan alone would say; a session reset (`connected` false then true) resets the
delivered counter and the lifecycle layer does not credit the old session's energy to the new
demand.

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
| Energy | kWh (`planEnergy`, `chargedEnergy`, `sessionEnergy`, `chargeRemainingEnergy`, `limitEnergy`, `vehicles.<name>.capacity`) | Wh (`battery_nominal_energy_capacity`); hours × W for deferrables (`operating_hours_of_each_deferrable_load`) | Wh (`energy_target_wh`) |
| Power | W (`chargePower`) | W (`nominal_power_of_deferrable_loads`, `battery_charge_power_max`, `def_current_power`, `maximum_power_from_grid`) | W (`nominal_power_w`, `p_min_w`, `current_power_w`, setpoints) |
| Current | A, per phase (`minCurrent`, `maxCurrent`, `chargeCurrents`) | none | none (derived from W at the active phase count and the site `Voltage`) |
| State of charge | percent; `vehicleSoc` is a float (number in `openapi.state.yaml`), `limitSoc` and plan `soc` are integer percent; 0 means unknown (`vehicleSoc`) or unset (`limitSoc`) | fraction 0 to 1 (`soc_init`, `soc_final`, `soc_target`, `battery_*_state_of_charge`) | percent in proposed fields; converted to fraction when passed on |
| Time | RFC 3339 with offset; seconds for durations (`planOverrun`, `chargeDuration`) | slot indices relative to the run start; `optimization_time_step` in minutes | ISO datetimes with offset, UTC internally |
| Phases | 0/1/3 configured, 1/2/3 active | none | 1 or 3 (proposed) |

Acceptance: a registration of 11 kWh for an 11 kW charger produces
`operating_hours_of_each_deferrable_load` of 1.0 h (or 2 timesteps of 30 min for a
semi-continuous load); a `soc_init` of 0.6 is sent for a `vehicleSoc` of 60, and 0.604 for a
`vehicleSoc` of 60.4 (a value of 60.4 is not a fraction and v0.18.6 rejects it); the response echoes the derived values so a reviewer
can check the arithmetic without reading code.

## H. Added in the 2026-11-04 revision

### R21. Tiers: a target, an optional deadline and a grid rule each

A single per-departure target with one grid rule cannot say "the grid may fill the car up to
X %, solar fills it beyond". The planner must be able to take several tiers for one vehicle,
each with:

1. **a target**: an SOC (fraction) or an energy, soft (R16);
2. **an optional deadline**: an instant by which the target should be met, or none;
3. **a grid eligibility**: whether energy for this tier may come from the grid, and where the
   limit lies (Q9).

**"Open-ended, no departure" is a first-class tier**, not an absence of R3. Its target is an
upper bound ("up to this much if it is cheap or free"), not an amount that must be delivered.

Example from LesIT1's installation (one installation, EMHASS v0.18.6, evcc 0.315.2): the car
is planned as two deferrables. A **floor** (top up to a minimum SOC by early morning; the only
EV energy allowed to come from the night grid) and an **opportunistic solar top-up with no
deadline at all**. In tier terms: tier 1 = target at the floor SOC, deadline early morning,
grid allowed; tier 2 = target at the desired SOC, no deadline, grid not allowed.

- Executor: evcc has no tier concept and no per-tier grid rule. The floor maps to vehicle
  `minSoc` (`POST /api/vehicles/{name}/minsoc/{n}`, `effectiveMinSoc`); a ceiling to
  `limitSoc` (0 is unset, R7). `effectivePlanTime`, `effectivePlanSoc` and `effectivePlanId`
  are read as inputs that can seed a tier's target and deadline; they are not written (R17).
  Repeating plans (`RepeatingPlan{weekdays 0 to 6, time "HH:MM", tz, soc, active}`) carry a
  different target per weekday, which is how a weekday commute and a weekend trip differ; this
  is read-only input here.
- Why a grid rule per tier has to be expressible: evcc's own optimizer (`evcc-io/optimizer`, schema `BatteryConfig` in `openapi.yaml`, field
  `charge_from_grid`, checked at `1205e7d`) knows the grid rule only as a boolean per battery:
  "can be charged from the grid, subject to the optimization" or "cannot be charged while power
  is drawn from the grid". A boolean per device cannot express "grid below X %, solar
  above". I did not check whether the optimizer models vehicles with an equivalent flag.
- Planner, today: tier 1 is a windowed deferrable load with an exact energy; tier 2 has no
  representation. A deferrable takes an exact energy and a window. The nearest thing to an
  optional load is `deferrable_load_max_cost`: the load runs in full or not at all, with a
  reward equal to the maximum cost, so it still cannot say "any amount up to X". A deadline past the horizon is clamped to the horizon end by the lifecycle
  layer, so an open-ended top-up registered as a demand means "all of this energy by the end
  of the horizon", the opposite of the intent. flexd cannot express tier 2 today (stated in
  #1, reply of 2026-11-03).
- Planner, phase 2: per-tier soft targets on the EV battery, a deadline that is optional (a
  tier without one binds to nothing but the horizon), and a grid-eligibility constraint per
  tier. The EMHASS power balance does not attribute energy to sources, so how a tier's
  "grid allowed" is formulated is the phase 2 design's to decide; this document only fixes
  that it must be expressible.
- Lifecycle layer: a demand without a deadline is representable (today it is not); an
  `open_ended` flag on `Demand` was considered and rejected because the aggregator could not
  honour it.

Acceptance: with the two-tier example, a plan for a night with a cheap price window contains
grid-sourced EV energy only up to the floor tier's target; the second tier's energy appears
only where the solar surplus covers it, whatever the price; the plan has no equality on the
tier-2 target, and a tier-2 target that cannot be met is a shortfall, not an infeasible solve.
A tier with no deadline never forces energy into the last slot of the horizon. Moving tier 1's
deadline earlier by two hours re-plans within one cycle without a re-registration.

### R22. One shared site import cap

The EV and the house battery draw on the same grid connection. A car and a battery grid
charging together can push the import past the main switch rating (seen on LesIT1's
installation, one installation).

- Planner, today: `maximum_power_from_grid` is a plant parameter (W) that accepts a scalar or
  a per-step list (`_prepare_power_limit_array`, `src/emhass/optimization.py`; a list of the
  wrong length draws a warning). It limits the grid import of the whole plan, so loads and
  batteries share it by construction.
- Planner, phase 2: the EV battery's charge and the house battery's charge are both inside
  that single cap; a phase 2 formulation must not give the EV its own import allowance on top.
  The cap is a per-step list, so a time-varying limit (a demand-charge window, a utility
  limit) works for the EV too.
- Second line: per-phase limits (upstream #622, "Support for three-phase
  maximum_power_from_grid", closed; I found no per-phase grid limit in
  `src/emhass/optimization.py` at v0.18.6 and did not trace why it closed) and evcc circuits
  limit current per phase or per group, below the plan if need be. A circuit can trim a charge
  below the planned power, so the delivered energy has to feed back into the next solve (R18).
- Lifecycle layer (proposed): reads the plan's grid import and flags a plan whose sum exceeds
  the cap; this is a check, not a second solver.

Acceptance: with `maximum_power_from_grid` of 11 kW for one step, a house battery grid-charging
at 5 kW and a 11 kW EV never appear together in that step above 11 kW of import (the sum of
`P_grid_pos` stays at or below the cap, whatever the individual limits). When an evcc circuit
trims the EV to 6 kW during the step, the missing energy appears in the next cycle's remaining
energy.

## Mapping summary

"Checked on" says the evcc release the evcc column was read on: `m` = master `daacfa7`
or `12ce81c`, `0.315` = LesIT1 on tag 0.315.2 (see "evcc versions per field").

| Requirement | evcc | Checked on | EMHASS v0.18.6 (verified) | Phase 2 (proposed in #610 / #1150) | Lifecycle layer |
|---|---|---|---|---|---|
| R1 charge-only | no loadpoint discharge API | m | deferrable load | `battery_discharge_power_max` = 0 | `type: ev` |
| R2 arrival | `connected`, `connectedDuration` | m | `start_timesteps_of_each_deferrable_load` | connected mask true | `window_start` |
| R3 departure, target | folded into R21 | | | | |
| R4 several windows | repeating plans (departures only) | m | one window per load | per-timestep connected list | one window per demand |
| R5 energy while away | `vehicleSoc` (float) on return, `vehicleRange` | m, 0.315 for type | none | `soc_on_return` or driving delta (a design round, #1) | consumer estimate |
| R6 SOC, observation time, staleness per source | `vehicleSoc`; no published timestamp (Q1); poll modes; no forced read | m, 0.315 | none (consumer converts) | `soc_init` list, re-anchor | `soc_percent`, observation time, source, per-source max age (proposed) |
| R7 usable capacity | `vehicles.<name>.capacity` kWh, `limitSoc` (0 = unset), `vehicleLimitSoc`, `effectiveLimitSoc`, `limitEnergy` | m, 0.315 | none | `battery_nominal_energy_capacity`, `battery_maximum_state_of_charge` | clip, reason in RFC 0001 |
| R8 losses | `chargedEnergy` meter-side vs `vehicleSoc` | m | none | `battery_charge_efficiency` | `charge_efficiency` (proposed) |
| R9 target per departure | folded into R21 | | | | |
| R10 min/max power, "off or at least p_min" | `minCurrent`, `maxCurrent`, `effectiveMin/MaxCurrent`, `phasesActive` | m | `nominal_power_of_deferrable_loads`, `minimum_power_of_deferrable_loads` | `battery_charge_power_max` plus a **semi-continuous charge variable** (new, not in v0.18.6 batteries) | `nominal_power_w`, `p_min_w`, `modulating` |
| R11 phase switching | moved to RFC 0001 | | | | |
| R12 current steps | moved to RFC 0001 | | | | |
| R13 interruptibility, wakes | moved to RFC 0001 | | | | |
| R14 no telemetry | `limitEnergy`, `planEnergy`, null `chargeRemainingEnergy`; `vehicleSoc` 0 = unknown | m, 0.315 for 0 | energy-based plan | SOC optional | unknown-SOC flag (RFC 0001) |
| R15 late arrival | `connected`, `planOverrun` | m | `start_timesteps` moves | connected mask | truncation flag (RFC 0001) |
| R16 never infeasible | `planOverrun` | m | lifecycle layer pre-shrinks | soft tier target with penalty (my proposal) | reason vocabulary in RFC 0001 |
| R17 responsibilities | `mode/{now\|off}`, `maxcurrent`, `minsoc`; `smartCostLimit`, `batteryBoost`, automatic mode off; evcc plans read, never written | m; `minsoc` 0.315; automatic mode: 0.318.0 code | `P_deferrable{n}`, `def_current_power` | `P_batt_{k}` | override detection in RFC 0001 |
| R18 feedback | `chargedEnergy`, `sessionEnergy`, `chargePower` | m | `def_current_power`, `def_current_state` | measured SOC re-anchor | measured delivered energy (RFC 0001) |
| R19 time zones | RFC 3339, `RepeatingPlan.tz` | m | `time_zone`, slot indices | same | tz-aware, UTC internal |
| R20 units | kWh, W, A, percent (`vehicleSoc` float) | m | Wh, W, fraction, slots | same as phase 1 | Wh, W, percent in, fraction out |
| R21 tiers | `minSoc` (floor), `limitSoc` (ceiling), `effectivePlanTime`/`effectivePlanSoc` read only; no per-tier grid rule | m, 0.315 for `minSoc` and `limitSoc` | exact-energy deferrable, no upper-bound tier | per-tier soft target, optional deadline, grid eligibility | a demand without a deadline (not representable today) |
| R22 shared import cap | circuits, per-phase limits | m | `maximum_power_from_grid` scalar or per-step list | one cap for EV and house battery | check on plan import |

## Open questions

Items I could not verify in the sources listed at the top. None is assumed true anywhere
above. Answers marked "answered by one installation" come from LesIT1's comment of 2026-10-19
in #1, from a single installation on evcc 0.315.2; they say how that installation behaves, not
what evcc does in general, and I did not re-verify them.

- **Q1. SOC observation time.** evcc keeps `socUpdated` in `core/loadpoint.go` but I found no
  state key or REST field that publishes it. *Answered by one installation (evcc 0.315.2):*
  there is no SOC timestamp on 0.315.2 either. Whether the websocket or MQTT publication
  carries a timestamp per value, or whether the executor's Home Assistant integration adds
  one, is still not verified. R6 now says why a read-time stamp is not a freshness signal.
- **Q2. Vehicle capacity in the state API. Closed.** `vehicles.<name>.capacity` ("Usable
  battery capacity in kWh") is in the `Vehicle` schema of `openapi.state.yaml`, on 0.315.2
  (LesIT1) and on master (`12ce81c`, me). The `capacity` fields I had found earlier belong to
  battery schemas.
- **Q3. Semantics of `smart` mode.** `api.ChargeModeString` on master accepts `off`, `now`,
  `smart`, `minpv` and `pv`, and `SetMode` normalises `pv`/`minpv` to `smart` with an
  always-charge flag. I did not trace what `smart` does when a loadpoint plan and a
  smart-cost limit are both set, so R17 lists all PV-oriented modes as "off when the planner
  drives". *Answered by one installation (evcc 0.315.2):* there is no `smart`; the
  installation uses `pv` plus vehicle `minSoc` for the floor and `now` for manual charging.
  That answers what is in use on 0.315.2, not what `smart` does on master.
- **Q4. Per-phase current limit versus total.** `maxCurrent` is documented per phase. Whether
  a 1p/3p charger's current limit applies before or after the executor's phase decision, and
  how `phasesActive` of 2 arises, is not verified beyond the key comment. *One installation:*
  cannot say, the charger is fixed three-phase. Still open; it belongs to the executor
  concerns now in RFC 0001.
- **Q5. Phase 2 field names.** Everything marked "proposed" for phase 2 (connected mask,
  `soc_on_return`, per-battery SOC target at departure) is taken from LesIT1's and
  scruysberghs's wording in #610 and #1150, not from code. The names are placeholders for
  this document. **Correction:** the **soft target with a penalty for the EV is my proposal
  (R16, R21), not LesIT1's from #610.** What LesIT1 said there is that re-anchoring touches
  the terminal-SOC equality and needs its own design round. A soft penalty is my reading of
  what he has argued elsewhere; the other quoted names are as he wrote them.
- **Q6. `def_current_power` versus the window end.** The flexd acceptance work observed that
  the planner extends the first slot's window when `def_current_power` is above zero; the
  precedence between a running load and a window that has already ended is not documented
  and needs checking in `optimization.py` at v0.18.6 before R17's override behaviour is
  relied on.
- **Q7. Energy-plan execution in `now` mode.** Whether the executor honours `planEnergy` and
  `planTime` while the loadpoint is in `now` mode, or only in `smart`, is not traced. It
  matters less since R17 stopped writing plans, but it still decides what a plan the person
  sets in evcc does while the planner drives `now`/`off`. *One installation:* does not use
  evcc plans, so no answer. Still open.
- **Q8. Executor-side feedback transport.** The cookbook reads executor state through the
  Home Assistant integration's sensors with placeholder names. Which of `chargedEnergy`,
  `sessionEnergy` and `vehicleSoc` that integration exposes, and under which entity ids, is
  outside the sources read; R18 names the executor's own keys instead. *Answered by one
  installation:* it reads evcc's REST `/api/state` directly, not the Home Assistant
  integration. That fixes the transport for that installation only.
- **Q9. Grid eligibility: a rule on the SOC at solve time, or on the SOC the plan reaches?**
  R21 needs a definition of "grid allowed only below X %". Either the rule reads the SOC at
  solve time (grid energy is allowed while the car starts the night below X %), or it reads
  the SOC the plan reaches (the plan may take grid energy up to X % and solar beyond it
  within one night). They give different constraints. Asked of LesIT1 in #1 on 2026-11-03;
  not answered yet, and the document does not choose.
