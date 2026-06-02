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
