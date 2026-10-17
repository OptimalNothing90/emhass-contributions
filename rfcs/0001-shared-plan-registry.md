# RFC 0001: Shared-plan coordination via an external registry sidecar (stateless EMHASS)

**Status:** Draft (Issue-filed)
**Discussion:** https://github.com/davidusb-geek/emhass/discussions/931
**Upstream context:** #824 (EV use-cases follow-up to #789); #1157 / #1158 (federated backend, `dry_run`); #610 / #1150 (multi-battery phases 1 to 3)
**Verification basis:** `audits/2026-05-31-emhass-evcc-coordination-synthesis.md` (facts F1–F16, build menu N1–N7); `prototypes/flexd/` against upstream `v0.18.6`
**Companion document:** `docs/ev-requirements.md` (EV charging requirements from the evcc side)
**Author:** OptimalNothing90
**Date:** 2026-06-02 · **Revised:** 2026-06-16, 2026-10-17

## Changelog

- **2026-10-17.** flexd is positioned as the demand-lifecycle layer in front of a stateless
  core, with explicit acceptance criteria (new section "What the sidecar is accountable for").
  The relation to the federated backend RFC (#1157) and to the `dry_run` runtime flag from
  draft PR #1158 is stated: `dry_run` is the core primitive the sidecar needs for context and
  what-if queries, the sidecar does not compete with a solver-side coordinator, and it shrinks
  to adapters and conformance tests if the core ever absorbs lifecycle. The "await the POST,
  then the GET belongs to my POST" assumption is replaced by request-bound results, with the
  current `generated_at` guard named as the interim. The sentence declaring N2 independent of
  multi-battery is reconciled with multi-battery phase 2; the EV requirements move to
  `docs/ev-requirements.md`. N1 is marked shipped (`GET /api/v1/plan`, upstream #995, in
  v0.18.x). Every reduction of a request now has to carry a machine-readable reason.
- **2026-06-16.** In-core registry replaced by an external sidecar after LesIT1's steer in
  #931. See the revision note below; the original text is kept in the appendix.
- **2026-06-02.** First version, in-core stateful registry. Filed as discussion #931.

## Revision note (2026-06-16): in-core registry → external sidecar

The first version of this RFC (preserved at the end of this document, collapsed) proposed
making EMHASS itself stateful, with a persistent registry living inside the core. In the
#931 discussion, LesIT1, who runs a multi-deferrable production setup, argued that the state
and its lifecycle belong outside EMHASS in a thin sidecar, leaving the core stateless and
recommend-only. That avoids the concurrency, atomic-write, and lifecycle-bug surface the
project has deliberately stayed away from, and it lines up with the #789 guard. This revision
adopts that. The registry moves out of EMHASS. The only thing EMHASS-core needs is a
machine-readable plan output, which is build item **N1** in the coordination synthesis.
Everything else (registration, persistence, lifecycle, recurrence) lives in the sidecar.

## Motivation

In a home with several flexible loads, they all compete for one scarce resource: PV surplus
and grid import/export headroom. Today each load is optimized on its own. evcc plans EV
charging by itself; a heat pump or hot-water tank runs on its own local surplus trigger;
EMHASS optimizes the home battery and its statically-configured deferrable loads. Nobody
allocates the scarce capacity across all of them. The result is first-come-first-serve
contention: a surplus appears, several loads jump on it independently, their combined draw
exceeds the surplus or a grid limit, loads trip or back off, and the system oscillates. It
happens even in summer, where surplus is finite at any given instant, and it gets worse in
the shoulder seasons.

EMHASS already solves the whole-house MILP that arbitrates this, and it already co-optimizes
competing deferrable loads inside a single call. Two things were missing in June 2026, and
neither is the solve itself:

1. **No persistent shared state across cycles.** EMHASS is stateless, one request at a time.
   There is no persistent notion of "the flexible loads currently in play". A multi-source
   setup (evcc, a heat pump, HA automations, later LLM agents) has no shared plan to
   contribute to. Each source rebuilds and resubmits the whole problem every MPC cycle.
2. **No machine-readable plan output.** `/action/*` returned a plain-text acknowledgement; the
   schedule was published to Home Assistant or written to `opt_res_latest.csv` (synthesis
   F11). Nothing handed a caller the structured plan back. This gap closed with
   `GET /api/v1/plan` (upstream #995, in the v0.18 line).

There are two ways to add the shared state. The original version of this RFC put it inside
EMHASS. The problem, raised by LesIT1 in #931 and consistent with #789, is that an in-core
registry makes EMHASS stateful: concurrency, atomic writes, file corruption, and demand
lifecycle all become core concerns the project has chosen to avoid. The alternative keeps
EMHASS stateless and puts the state in a **sidecar**: a small separate service that owns the
registry and renders the active demands down into an ordinary stateless optim call. The
solver never knows the registry exists. This RFC takes the sidecar route. The sidecar exists
as a prototype under `prototypes/flexd/` in this repository ("flexd" is a working name).

## Architecture

```
  consumer events                      sidecar (external, our layer)            EMHASS (stateless core)
  (EV plugged in,        register /    ┌───────────────────────────┐
   washer started,  ───  refresh / ──▶ │  registry: active demands  │
   pool season)          withdraw      │  + lifecycle (expires_at)  │
                                       │  + recurrence rules        │
                                       └───────────┬───────────────┘
                                                   │ each MPC cycle:
                                                   │ aggregate → deferrable payload
                                                   ▼
                                       POST /action/naive-mpc-optim (runtimeparams)  ──▶  MILP solve
                                                   ▲                                       │
                                       GET /api/v1/plan  (structured plan, N1) ◀───────────┘
                                                   │
                                       sidecar holds the plan; consumer reads it and actuates
```

Placement against the #789 guard (synthesis F16): the registry and any actuation are glue,
outside EMHASS core. EMHASS stays the MILP optimizer and nothing more. The sidecar submits
demands through the **existing** `/action/*` runtime-params path, the same mechanism a
multi-deferrable operator already uses by hand today, so no new inbound API is added to
EMHASS. The one core addition was the plan output (N1) so the sidecar can read the result
back without scraping a CSV.

## What the sidecar is accountable for (2026-10-17)

The sidecar is the **demand-lifecycle layer** in front of a stateless core. It is not a second
optimizer and not a coordinator between solvers. Its job is everything that happens to a
demand between the moment a consumer raises it and the moment the consumer reads a setpoint
back: registration, ownership, expiry, persistence across restarts, mapping onto the core's
runtime parameters, attribution of the result back to the demand, and an honest account of
what the mapping had to change. The core keeps solving; the sidecar keeps the books.

The division of labour in one table:

| Concern | Sidecar | EMHASS core |
|---|---|---|
| Who wants what, by when, at which power | owns (registry) | receives per call as runtime params |
| Lifecycle: expiry, refresh, withdrawal, restart | owns | none (stateless by design) |
| Ownership: a source cannot overwrite another's demand | owns | none |
| Mapping a demand to `number_of_deferrable_loads` and friends | owns | validates the payload |
| Solving the whole-house problem | never | owns |
| Reading the plan back and attributing slots to demands | owns | serves `GET /api/v1/plan` |
| Telling the consumer what got reduced and why | owns | reports `optim_status` per run |
| Actuation | never | never |

### Acceptance criteria

These are the criteria a sidecar implementation has to meet before it is trusted with a real
household. They were sharpened by LesIT1's adversarial review of the prototype
(OptimalNothing90/emhass-contributions#1) and by the two fix batches that followed; the
criteria are stated here so the design, not the prototype, is what gets held to them.

1. **Withdrawn reads OFF within one poll on every transport.** When a consumer withdraws a
   demand, or the demand expires, the next read of that demand's setpoint on every transport
   the sidecar offers (REST, plain-value HTTP, retained MQTT) says OFF / 0 W, before the next
   solve, not after it. A consumer never has to wait a cycle to learn that its demand is gone.
2. **A restart loses no demand and no adopted plan.** After a process restart, every demand
   that was active and unexpired is active again with the same expiry, and the last adopted
   plan is served as it was, marked stale by age rather than forgotten. A structurally valid
   registry file with one corrupt entry keeps every valid entry and logs the bad one.
3. **Remaining energy never produces an infeasible semi-continuous solve.** A device that runs
   at nominal power or not at all is asked for whole timesteps (rounded up, capped at its
   window); a device that modulates is asked for fractional hours. In neither case does the
   sidecar hand the core an energy target that cannot be met inside the window at the
   declared power, and a demand whose window has closed is passed as inactive rather than
   pinned on with zero hours.
4. **Plan attribution survives a plan switch.** Elapsed energy for a standing or long-running
   demand is credited from the plan that was actually in force at each instant, including the
   seconds between a new plan's adoption and the cycle boundary. Switching plans mid-cycle
   neither double-counts nor drops energy.
5. **Every reduction carries a machine-readable reason.** When the mapping changes what a
   consumer asked for, the per-demand view says so with a stable, enumerable field, not a log
   line. The current vocabulary is `truncated` (energy does not fit the window at the declared
   power), `clamped` (deadline beyond the horizon), rounded to whole slots (`timesteps` versus
   the requested hours), and `unschedulable` (window closed or degenerate). This is the
   sidecar-side counterpart of the explainability request in upstream #1185: a consumer, human
   or agent, must be able to answer "why did I get less than I asked for" from the response
   alone.
6. **Ownership is enforced, not assumed.** A `source` can refresh or withdraw only the demands
   it registered. A register with an id another source already owns is rejected.
7. **Bad input is rejected at the door.** Non-finite numbers, absurd magnitudes, naive
   datetimes and malformed ids never reach the registry file, on any transport, because one
   bad entry would otherwise poison every solve until its expiry.

The companion document `docs/ev-requirements.md` applies the same discipline to one demand
type, the EV, and lists the acceptance scenarios an EV demand has to pass.

## Relation to the federated backend (#1157) and to `dry_run` (#1158)

The federated backend proposed in #1157 (draft PR #1158, ameetdesh) coordinates several
**solvers** by prices at the meter: EMHASS's own models, a dynamic-programming battery solver,
or an outside participant such as evcc, each answering "what would you do at these prices".
That is a coordination problem between optimizers. This RFC addresses a different problem:
one optimizer, many **consumers** that come and go. The two do not compete.

- The sidecar sits in front of whichever solving path the core offers. If a user turns on a
  coordinated backend, the sidecar's payload is still ordinary runtime parameters and its
  read-back is still `GET /api/v1/plan`. Nothing in this RFC assumes the default MILP.
- The sidecar never takes part in price iteration. Its demands are inputs to the solve, not a
  participant with a private cost.
- If the core ever absorbs demand lifecycle itself (a registry endpoint, run-keyed demands,
  or a participant interface that carries expiry and ownership), the sidecar shrinks to what
  cannot live in the core: transport adapters for consumers that speak plain HTTP or MQTT, and
  the conformance tests behind the acceptance criteria above. That outcome would be fine. The
  acceptance criteria are written so that they survive the move.

**`dry_run` is the core primitive this RFC depends on next.** In #931 on 2026-08-30, MMicieli
proposed that a sidecar distinguish three registration kinds: a *demand* (an energy
requirement to schedule), a *context* entry (temporary information that changes an input or a
constraint: an empty house for three weeks, a smoke event depressing PV, a battery SOC floor
by a given time), and a *query or scenario* (inspect or simulate without changing
production). LesIT1 replied that demand and context share one lifecycle and need no new
machinery, and that what-if is less free than it looks because a solve writes
`opt_res_latest.csv`, feeds `continual_publish` and updates the plan store, so a scenario
solve against the live instance replaces the live plan. Run-keyed or non-persisting results
were named as the prerequisite.

`dry_run` as specified in #1158 is exactly that prerequisite: the same request, a real solve,
the plan returned in the HTTP response, and nothing written (no results CSV, no plan store, no
last-run record, no publish, a private `Optimization` so the live cache and warm start are
untouched). With it, the sidecar's roadmap becomes:

1. **Demands** (today): folded into the live solve, result read from `GET /api/v1/plan`.
2. **Context entries** (after the shadow run): same registry, same `expires_at` and
   ownership, folded into validated runtime parameters (for example `soc_target` and
   `soc_target_timestep` for the SOC-floor case) instead of a deferrable slot.
3. **Queries and what-if** (needs `dry_run`): the sidecar submits the live payload plus the
   hypothetical change with `dry_run: true` and returns the plan to the asker without touching
   the live plan. "What if the car had to be at 80 % by 17:00" and "what does the import cap
   cost me" are this kind of request.

Two properties of `dry_run` matter to the sidecar specifically, both already raised in #1157
by MMicieli and LesIT1: a release that does not know the flag must not silently run a live
solve (so the sidecar gates on a version or capability signal before sending it), and
actions that cannot honour it should reject it rather than ignore it. This RFC supports
splitting `dry_run` out of #1158 into its own PR; the sidecar is a concrete user of it
independent of the federated backend.

## EMHASS-core change: N1, structured plan output (shipped)

A read-only endpoint that returns the most recent optimization result as JSON.

- `GET /api/v1/plan` — the latest `opt_res` as JSON records, carrying `emhass_schema_version`
  and `generated_at`. Shipped upstream as #995; the sidecar prototype builds against the
  pinned release `v0.18.6`.
- Columns follow the existing plan-output schema (`docs/plan_output_schema.md`, #835); the
  version follows `EMHASS_SCHEMA_VERSION`.
- It mirrors `GET /api/v1/last-run` (#851), which already returns run metadata.
- Additive, read-only, non-breaking. The HA publish and CSV paths are untouched.

### Binding a result to the request that produced it

The June version of this RFC assumed that because `/action/*` is awaited and EMHASS is a
single writer, the plan returned by a following `GET /api/v1/plan` is the one the POST just
produced. That holds only when the sidecar is the sole caller of the instance. LesIT1's
production setup (an external MPC loop every 15 minutes) and MMicieli's run-correlation point
in #931 both show the assumption is not safe in general: a second caller, or a re-served
previous plan after an infeasible solve, breaks it silently.

The target is **request-bound results**: a solve that returns its own plan in its own
response, or a plan store keyed by a run id that the response names. `dry_run` already
returns the plan in the response for the non-persisting case; a run id on the persisting case
would close the gap for live solves. Until one of those exists, the sidecar uses an interim
guard: it adopts a plan only if `status` is `ok`, the schema version is known, and
`generated_at` is strictly newer than the last adopted plan's. The guard rejects a re-served
plan; it cannot tell two fresh plans from two callers apart, so the documented operating rule
remains one caller per instance.

## The sidecar (external, not an EMHASS change)

Described here so the architecture is legible, but it is not part of the EMHASS ask. It owns:

- **Consumer API.** `register` / `refresh` / `withdraw` / `list` for demands. A required
  `expires_at` plus idempotent refresh means a consumer that dies just ages out, with no
  orphaned demand wedged in the plan. Refresh never shortens a demand and never revives an
  expired one. This API is internal to the sidecar; it never reaches EMHASS.
- **Persistence.** The registry as JSON (no pickle), single-writer with atomic temp-file +
  rename; the adopted plan and its demand-to-slot mapping persisted the same way.
- **Aggregation.** Each cycle, fold the active demands into a standard deferrable-load
  runtime-params payload for EMHASS, aligned to the core's own timestep grid, with the
  reduction reasons from acceptance criterion 5 recorded per demand.
- **Recurrence.** A recurrence rule per registration for standing/seasonal loads (a pool pump
  whose hours shift monthly), rather than materialized instances.

A registered demand reuses the runtime-schema-family vocabulary (`param_definitions.json`,
`runtime_params.json` / #915) rather than inventing a new shape: essentially a persisted
runtime deferrable-load demand plus `priority`, `source`, and a lifecycle.

## Threat model (split by layer)

Per the #808 maintainer comment, the concern is code injection. Splitting the design splits
the surface:

- **EMHASS-core side: near-zero new surface.** The only addition is `GET /api/v1/plan`. It is
  read-only, takes no input, persists nothing, and returns the same data EMHASS already
  publishes to HA. The injection-risk surface is unchanged from today. `dry_run`, when it
  lands, removes writes rather than adding them.
- **Sidecar side: owns the persistence risk, out of core.** JSON-only (no pickle, no
  deserialization of code), validated on load with hand-rolled checks, writes confined to the
  sidecar's own data directory, ids never used to build filesystem paths, single-writer atomic
  write, non-finite and out-of-range numbers rejected before persistence. A bad demand
  persists only until its `expires_at`. None of this touches EMHASS.

The pivot's headline security effect: the new EMHASS attack surface drops from "stateful
persistence with a widened blast radius" to one read-only GET.

## Backward compatibility

- `GET /api/v1/plan` is additive. With no caller, nothing changes.
- `/action/*`, configuration, and the HA publish path are unchanged.
- No new runtime dependency (stdlib JSON on the sidecar side; nothing new in core).
- Default config still works unchanged.

## Roadmap and sequencing (coordination synthesis N1–N7)

This RFC delivered **N1**. The rest is sequenced, not bundled:

- **EMHASS-core siblings** (separate RFCs/PRs, later): **N2** EV with a state of charge.
  The June text called N2 "independent of multi-battery"; that was true of the deferrable-
  load-plus-accumulator route (synthesis b-i) and is no longer the route of record. Since
  then LesIT1's multi-battery programme (#610) shipped phase 1 (N stationary batteries,
  #1032, in 0.18.0), has phase 3 (per-inverter modelling, #1150) in design, and names
  phase 2, an intermittently connected battery with SOC re-anchoring on reconnection and a
  per-battery SOC target at departure, as the home of V2G and the EV. N2 therefore becomes
  the EV **requirements** input to phase 2, written now from the evcc side in
  `docs/ev-requirements.md`, rather than a competing core model. Until phase 2 exists, the
  sidecar maps an EV to a windowed deferrable load, charge-only, and says so in the
  per-demand reasons. The **load-priority MILP** (EMHASS has no inter-load ranking today)
  and **N5** soft-constraint / never-infeasible behaviour remain their own sibling items.
- **Core primitives this RFC consumes:** `dry_run` (#1158, split requested), and a run id or
  request-bound plan for live solves (see "Binding a result").
- **Sidecar features** (not EMHASS RFCs): context entries as a second registration type,
  what-if queries over `dry_run`, template store, MQTT intake, recurrence/seasonal
  enablement, per-source identity, persistence. The shadow run against LesIT1's setup gates
  the move from demands to context.
- **Minimal first slice:** delivered (`GET /api/v1/plan`, #995) and consumed by the prototype.

## Known limitations (interim, with a closure path)

- **EV is modeled as a deferrable load, lossy.** The sidecar maps an EV charge need to a
  deferrable with an energy target and a window. It cannot express an SOC curve
  ("40% → 80% by 07:00"), several availability windows per horizon, or energy used while
  away (synthesis F10). The closure path is multi-battery phase 2; the requirements are in
  `docs/ev-requirements.md`. Until then the mapping is an approximation, not a permanent
  ceiling, and the consumer sees it as such through the reduction reasons.
- **No user-intent priority.** When not everything fits, conflicts fall to the existing cost
  objective rather than an explicit per-load priority, until the priority sibling lands.
- **One caller per instance.** Until results are request-bound, a second caller of the same
  EMHASS instance can make the sidecar adopt a plan it did not ask for. The `generated_at`
  guard narrows but does not close this.
- **No what-if without `dry_run`.** A scenario solve against the live instance would replace
  the live plan; the sidecar does not offer queries until the flag exists upstream.

## Open questions

- **Sidecar placement.** Standalone companion repo, a small community org, or something EMHASS
  references. This is the maintainer's call to steer; the only hard requirement is that it
  stays separate from and non-binding on EMHASS core.
- **Run identity on live solves.** Whether the persisting actions should return a run id (or
  the plan itself) in the response, so that request binding does not depend on `dry_run`.
  Core question; raised by MMicieli and LesIT1 in #931.
- **Reason vocabulary.** Whether the per-demand reduction reasons (`truncated`, `clamped`,
  `timesteps`, `unschedulable`) should align with whatever machine-readable reasons the core
  adopts under #1185, so a consumer reads one vocabulary end to end.
- **Recurrence model.** The exact shape of the recurrence rule and seasonal enablement
  (sidecar concern).
- **Per-source identity.** Ownership by `source` name is enforced; whether a token or
  namespace should back it on an unauthenticated LAN is open. Sidecar concern.
- **Outcome richness.** How far beyond the reduction reasons the per-demand result should go
  (deferred, reduced, rejected). Sidecar concern.
- **MQTT intake.** Whether demands are also submittable over MQTT. A sidecar transport
  feature, not an EMHASS change.

---

## Appendix: superseded original (in-core registry, S2)

<details>
<summary>Original RFC 0001 as posted 2026-06-02 — proposed an in-core stateful registry. Superseded 2026-06-16 by the sidecar design above, after #931 feedback. Kept for the discussion context LesIT1's comment responds to.</summary>

# RFC 0001: EMHASS as a stateful shared-plan service (persistent flexible-load registry)

**Status:** Issue-filed
**Discussion:** https://github.com/davidusb-geek/emhass/discussions/931
**Upstream context:** #824 (EV use-cases follow-up to #789)
**Author:** OptimalNothing90
**Date:** 2026-06-02

## Motivation

In a home with several flexible loads, they all compete for the same scarce resource: PV surplus and grid import/export headroom. The loads differ in nature. Some are ad-hoc (an EV charge session, a washing machine, a dishwasher), some are predictable and recurring (heat pump, hot water, heating), and some are seasonal (a pool pump). Today each one is optimized on its own:

- evcc plans EV charging by itself, using price and PV heuristics;
- the heat pump or hot-water tank runs greedily on its own local surplus trigger;
- EMHASS optimizes the home battery and its statically-configured deferrable loads.

Nobody allocates the scarce capacity across all of them. The result is first-come-first-serve contention: a surplus appears, several loads jump on it independently, their combined draw exceeds the available surplus or a grid limit, loads trip or back off, and the system oscillates. It happens even in summer, where surplus is still finite at any given instant, and it gets worse in the shoulder seasons.

EMHASS already solves the whole-house MILP that could arbitrate this, but it does so statelessly, one request at a time. Each caller has to resend the entire problem on every call, and there is no persistent notion of "the flexible loads currently in play" or "the current plan". So a multi-source setup (evcc, a heat pump, HA automations, and eventually LLM agents) can't contribute demands to one shared plan. Each source would have to own and resubmit the whole problem, which is what produces the isolated, conflicting optimizations above.

There is an obvious alternative: keep EMHASS stateless and put a stateful aggregator in front of it, one that continuously collects every demand from every source and resubmits the full problem each cycle. The trouble is that the aggregator is the hard part. It has to know about, poll, and re-capture all the sources on every tick, which makes it a complex, tightly-coupled, central component. Holding the registry inside EMHASS inverts that. Each consumer becomes a simple trigger-based integration: it fires a register or withdraw when its own event happens (the EV is plugged in, the washing machine is started), and otherwise does nothing. EMHASS already holds the optimization, so it is the natural place to aggregate. The integration burden drops from "build a stateful all-source aggregator" to "POST one demand when your event fires". That is the main reason the state belongs in EMHASS rather than in every integrator.

The stateless model also blocks the LLM-ready direction. For EMHASS to be a first-class planning interface for AI tooling, agents need to query the current plan and propose or withdraw demands against a persistent shared state, instead of reconstructing the whole optimization problem on every interaction.

## Proposed change

Add an optional, persistent flexible-load registry to EMHASS, turning it into a stateful shared-plan service while keeping it recommend-only.

The core primitive is generic: any consumer registers a demand through one uniform API, whether that demand is an EV charge need, a thermal target, or a generic deferrable load. The contention example above spans several consumers, but the mechanism itself is consumer-agnostic. The consumer-specific work stays out of scope here: how a given consumer (evcc for an EV, or a heat pump for a thermal target) builds and submits its demand, and how the returned plan then gets actuated. Each consumer is its own follow-on piece, a public usage example plus that consumer's own (often private) glue. Note that a demand (what the consumer needs) and actuation (how the plan is carried out) are separate concerns; actuation, including any device-signalling protocol, stays on the consumer side.

1. Registry (the persistent state). A set of registered flexible demands. Each entry carries its constraints (energy or SoC target, deadline window, min/max power, charge-only flag), a `priority`, a `source` id, and a lifecycle status (active or expired).
2. One shared plan, full re-solve. On each optimization tick (MPC), EMHASS solves the entire registry together with the battery, base load, and forecasts into a single plan. Because every solve considers all active demands at once, arrival order no longer decides the outcome (no first-come-first-serve admission), and the combined draw can't exceed the limits, since the joint power balance forbids it. Resolving conflicts by user intent, meaning which load yields when not everything fits, needs an explicit load `priority` that EMHASS doesn't have yet. Until the sibling priority RFC lands, conflicts fall to the existing cost objective rather than to user priority. So this RFC on its own delivers overshoot-prevention and one shared plan; priority-based arbitration is left to the sibling.
3. Inbound admission API. Callers submit, update, or withdraw a registered demand. EMHASS re-solves and returns the new plan plus a per-demand outcome (for example: fully scheduled, deferred, reduced, or rejected as infeasible at this priority). This is the "submit; if feasible, adopt into the shared plan" behaviour, done as a full re-solve rather than a greedy incremental merge.
4. Recommend-only is preserved. EMHASS returns the plan; it never actuates. Callers (Node-RED, HA, or a glue layer) read the plan and drive the hardware. EMHASS never calls out to a device or another service; submissions are inbound only.
5. Opt-in containment. The registry is additive and optional. With an empty or unused registry, the optimization path is identical to today's stateless solve.

Notes on the demand space:

- The shared plan unifies static config with dynamic registrations. Predictable loads (hot water, heating) that EMHASS already models via `thermal_config` stay as configuration; ad-hoc loads (EV session, washing machine, dishwasher) arrive through the registry; seasonal ones (pool pump) are standing entries enabled per season. All of them feed the one solve. The registry is additive, not a replacement for existing config, and it doesn't have to "own" the static loads in order to arbitrate against them.
- Templates. A registered demand can be fully specified inline, or it can reference a template stored in EMHASS: a reusable named load profile (`dishwasher-eco`, `pool-pump-summer`) built on EMHASS's existing fixed-profile deferrable-load definitions, so recurring loads don't have to resend their shape every time.
- Most "started" loads are shiftable within a window, not fixed. A resident plugging in the EV or starting an appliance is a trigger to register a `shiftable` demand with a window, not an immovable load: EV → `[now, +3h]` (or by departure); washing machine → `[now, +2h]`; a dishwasher with a built-in night delay → `[02:00, 06:00]`. EMHASS schedules within the window. The genuinely immovable case (a dumb appliance with no delay, already running) is the rare `committed` mode, which is account-only: EMHASS can't move it but registers it so other loads yield. `hybrid` means run on surplus or cheap power, but guaranteed done by a deadline. Which mode applies is the EMHASS user's per-load preference.
- Every entry has a mandatory timeout and an update path. A registered load carries a required `expires_at`, so stale entries drop automatically and a consumer that registers but never withdraws can't leave a zombie demand. Standing or seasonal loads stay alive by refreshing via `PUT`, and the same `PUT` updates a changing demand (a new SoC, a moved deadline).

The registry is the concrete form of the long-parked "persistent flexible-load registry" idea (follow-up to #824) and the basis for the LLM-ready goal.

## API / contract

New, additive endpoints (sketch; exact paths still open). They all live under the existing `/api/v1` namespace, consistent with `/api/v1/last-run`. Transport here is REST; an MQTT intake is a possible follow-on (see Open questions).

- `POST /api/v1/registry/loads` — register a flexible load; returns its id and post-solve outcome.
- `PUT /api/v1/registry/loads/{id}` — update an existing load (new target/deadline/SoC), or refresh its timeout.
- `DELETE /api/v1/registry/loads/{id}` — withdraw a load.
- `GET /api/v1/registry/loads` — list active registered loads.
- `GET /api/v1/plan` (or an extension of `GET /api/v1/last-run`) — the current shared plan as structured JSON, i.e. the recommendation.

A registered load reuses the runtime-schema-family vocabulary rather than inventing a new one. It is essentially a persisted runtime deferrable-load demand plus `priority`, `source`, and a lifecycle:

```jsonc
{
  "id": "ev-loadpoint-0",          // server-validated; NOT used as a filesystem path
  "source": "evcc",
  "type": "ev | thermal | generic",
  "flexibility": "shiftable | committed | hybrid",  // user preference; committed = run-now, account-only
  "energy_target_wh": 24000,        // OR soc_target + capacity_wh
  "deadline": "2026-06-03T07:00:00+02:00",
  "window_start": "2026-06-02T20:00:00+02:00",
  "p_min_w": 1400,
  "p_max_w": 11000,
  "charge_only": true,
  "priority": 1,
  "expires_at": "2026-06-03T08:00:00+02:00"   // mandatory; stale entries auto-drop, refreshable via PUT
}
```

The same object shape serves every consumer. An EV (shown above), a heat-pump thermal target, and a generic load (washing machine, dishwasher, pool pump) differ only in their field values, not in structure. A demand can also carry `"template": "<name>"` in place of the inline fields, referencing a profile stored in EMHASS.

- Demand fields align with `param_definitions.json` and `runtime_params.json` (the runtime-schema-family; `runtime_params.json` shipped as #915).
- Plan output reuses the plan-output schema (`docs/plan_output_schema.md`, #835) and is versioned by `EMHASS_SCHEMA_VERSION`.
- Load `priority` depends on a load-priority MILP capability that EMHASS doesn't have today (there is no inter-load ranking). That is proposed as a sibling RFC, not folded in here.

## Threat model

Per the #808 maintainer comment, the focus is code injection. The new surface here is persistence:

- No pickle, no arbitrary deserialization. The registry is persisted as JSON and validated on load by hand-rolled checks (no schema-validator dependency, consistent with the openapi generator). A malformed or unexpected file is rejected, not executed.
- No path traversal. Writes are confined to the existing `data_path`, the same directory already used for `opt_res_latest.csv`. Load `id`s are server-generated or validated and are never used to build filesystem paths.
- No shell-out, no DB, no `eval`. Registry mutations are pure data, validated against the demand schema.
- Corruption-safe writes. A single writer (the serving process), with an atomic write via temp-file and rename.
- The API takes JSON validated against a fixed shape, the same injection-risk class as the existing `/action/*` runtime-params intake. Persistence does widen the blast radius, though: a bad demand persists across every solve until its `expires_at`, where a stateless POST only affects one solve. The mandatory timeout bounds that, and invalid entries are rejected at the API and never persisted.

## Backward compatibility

- Fully opt-in. With no registered loads, the solve is functionally identical to today's; the registry contributes nothing to the optimization. The existing `/action/*`, configuration, and HA publish paths are unchanged.
- Stateless callers keep working. A caller that ignores the registry and POSTs the full problem (as today) is unaffected. The registry is an additional way to drive EMHASS, not a replacement.
- No new hard dependency (stdlib JSON persistence; nothing new at runtime).
- Default config still works unchanged.

## Open questions

- Recurrence and seasonal enablement. Every entry now carries a mandatory `expires_at` (decided above). What is still open is the recurrence model for standing loads: the auto-refresh cadence, and calendar or seasonal enablement (a pool pump active only in summer, say), via explicit re-`PUT` or a declared schedule.
- MQTT intake. Should demands also be submittable over MQTT (devices or HA publishing to a topic) alongside REST/v1? The primitive is transport-agnostic, so the recommendation is a separate follow-on RFC for an MQTT transport adapter rather than expanding this one.
- Template store. How stored load templates (the reusable profiles referenced by `template`) are defined, versioned, and managed. Possibly a follow-on RFC rather than part of this one.
- Priority semantics. Strict ordering versus weighted soft-penalty, and confirming this lands as a sibling RFC (load-priority MILP) rather than here.
- Persistence location and concurrency under multi-process or HA-addon deployments (the single-writer assumption, the lock strategy).
- Identity and authorization. EMHASS's API is usually local and unauthenticated. With multiple sources registering, should a `source` own its entries, so one source can't overwrite or withdraw another's, by accident or otherwise? Probably simple per-source namespacing or a token; TBD.
- Outcome richness. How detailed the per-demand admission result should be for v1: a minimal feasibility flag, or the fuller deferred/reduced/rejected detail.
- Consumer adapters are separate artifacts. Each consumer (evcc/EV first, as the cleanest case with precise demand, actuation, and feedback; then heat-pump/thermal; then generic loads) is specified outside this RFC, as a public usage example plus that consumer's own (often private) glue. This RFC stays consumer-agnostic: it neither mandates nor depends on the evcc/evopt contract, nor on any device actuation protocol.
- Minimal first slice. The smallest reviewable PR that lands the registry opt-in without the priority feature (a single-demand registry, full re-solve, JSON persistence), to validate the direction before the larger surface.

</details>
