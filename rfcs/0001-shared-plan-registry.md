# RFC 0001: EMHASS as a stateful shared-plan service (persistent flexible-load registry)

**Status:** Issue-filed
**Discussion:** https://github.com/davidusb-geek/emhass/discussions/931
**Upstream context:** #824 (EV use-cases follow-up to #789)
**Author:** OptimalNothing90
**Date:** 2026-06-02

## Motivation

Multiple flexible loads in a home compete for the same scarce resource — PV surplus and grid-import/-export headroom. They span **ad-hoc/event** loads (an EV charge session, washing machine, dishwasher), **predictable/recurring** loads (heat pump, DHW, heating), and **seasonal** ones (pool pump). Today each is optimized **in isolation**:

- evcc plans EV charging on its own (price/PV heuristics),
- the heat pump / DHW runs greedily on its own local surplus trigger,
- EMHASS optimizes the home battery + its statically-configured deferrable loads.

Nobody allocates scarce capacity across all of them. The result is **first-come-first-serve contention**: a surplus appears, several loads jump on it independently, their combined draw overshoots the available surplus or a grid limit, loads trip/back off, and the system oscillates. This happens even in summer (surplus is finite at any instant), and gets worse in shoulder seasons.

EMHASS already solves the whole-house MILP that *could* arbitrate this — but **statelessly, per request**. Each caller must re-send the entire problem every call, and there is no persistent notion of "the flexible loads currently in play" or "the current plan." A multi-source setup (evcc + heat pump + HA automations + LLM agents) therefore cannot contribute demands to **one shared plan**; each would have to own and resubmit the whole problem, which is exactly what produces the isolated, conflicting optimizations above.

**Why this belongs in EMHASS, not a bolt-on aggregator.** One could keep EMHASS stateless and place a stateful aggregator in front that continuously collects every demand from every source and re-submits the full problem each cycle. But that aggregator *is* the hard part: it must know about, poll, and re-capture **all** sources on every tick — a complex, central, tightly-coupled orchestrator. Holding the registry **inside** EMHASS inverts this: each consumer becomes a simple, **trigger-based** integration that fires a register/withdraw when its own event occurs (EV plugged in, washing machine started) and otherwise does nothing. EMHASS — the component that already holds the optimization — becomes the natural aggregation point. The integration burden drops from "build a stateful all-source aggregator" to "POST one demand on your trigger." This is the core reason the state belongs in EMHASS rather than in each integrator.

This also blocks the LLM-ready direction: for EMHASS to be a first-class planning interface for AI tooling, agents must be able to **query the current plan** and **propose or withdraw demands** against a persistent shared state — not reconstruct the full optimization problem on every interaction.

## Proposed change

Add an **optional, persistent flexible-load registry** to EMHASS, turning it into a stateful shared-plan service while remaining recommend-only.

The core primitive is generic: **any consumer registers a demand** — an EV charge need, a thermal/DHW target, a generic deferrable load — through one uniform API. The contention example above spans several consumers, but the mechanism itself is **consumer-agnostic**. Consumer-specific work — how a consumer (e.g. evcc for an EV, or a heat pump for a thermal target) builds and submits its **demand**, and how the returned plan is then **actuated** — is **out of scope here**: each consumer is its own follow-on artifact — a public usage example plus that consumer's own (often private) glue. A *demand* (what the consumer needs) and *actuation* (how the plan is carried out) are distinct concerns; actuation, including any device-signalling protocol, stays consumer-side.

1. **Registry (the persistent state).** A set of registered flexible demands. Each entry carries its constraints (energy/SoC target, deadline window, min/max power, charge-only flag), a `priority`, a `source` id, and lifecycle status (active/expired).
2. **One shared plan, full re-solve.** On each optimization tick (MPC), EMHASS solves the **entire** registry together with the battery, base load and forecasts into **one** plan. Because every solve considers all active demands at once, arrival order no longer decides outcomes (**no first-come-first-serve admission**) and the combined draw cannot overshoot — the joint power balance forbids it. *Resolving conflicts by user intent* (which load yields when not everything fits) requires explicit load `priority`, which EMHASS does not have today; until the sibling priority RFC lands, conflicts fall to the existing cost objective, not user priority. **This RFC alone delivers overshoot-prevention + one shared plan; priority-arbitration is the sibling.**
3. **Inbound admission API.** Callers *submit/update/withdraw* a registered demand. EMHASS re-solves and returns the new plan plus a per-demand outcome (e.g. *fully scheduled / deferred / reduced / rejected-infeasible-at-this-priority*). This is the "submit; if feasible, adopt into the shared plan" behaviour — but as a full re-solve, not a greedy incremental merge.
4. **Recommend-only preserved.** EMHASS returns the plan; it never actuates. Callers (Node-RED / HA / a glue layer) read the plan and drive hardware. EMHASS never calls out to a device or another service — submissions are **inbound only**.
5. **Opt-in containment.** The registry is additive and optional. With an empty/unused registry, the optimization path is identical to today's stateless solve.

Notes on the demand space:

- **The shared plan unifies static config with dynamic registrations.** Predictable loads (DHW, heating) that EMHASS already models via `thermal_config` stay as configuration; ad-hoc loads (EV session, washing machine, dishwasher) arrive through the registry; seasonal ones (pool pump) are standing entries enabled per season. All sources feed the **one** solve — the registry is *additive*, not a replacement for existing config, and does not have to "own" the static loads to arbitrate against them.
- **Templates.** A registered demand may be fully specified inline **or** reference an EMHASS-stored **template** — a reusable named load profile (e.g. `dishwasher-eco`, `pool-pump-summer`) building on EMHASS's existing fixed-profile deferrable-load definitions — so recurring loads need not re-send their shape each time.
- **Most "started" loads are shiftable within a window — not fixed.** A resident plugging in the EV or starting an appliance is a *trigger* to register a `shiftable` demand with a window, not an immovable load: EV → `[now, +3h]` (or by departure); washing machine → `[now, +2h]`; a dishwasher with a built-in night delay → `[02:00, 06:00]`. EMHASS schedules within the window. The truly immovable case (a dumb appliance with no delay, already running) is the rare `committed` mode — **account-only**: EMHASS can't move it but registers it so other loads yield. `hybrid` = run on surplus/cheap but guaranteed done by a deadline. Which mode applies is the EMHASS user's per-load preference.
- **Every entry has a mandatory timeout + an update path.** A registered load carries a required `expires_at`; stale entries auto-drop, so a consumer that registers and never withdraws cannot leave a zombie demand (a safety default aligned with the failsafe philosophy). Standing/seasonal loads stay alive by *refreshing* via `PUT`; the same `PUT` updates a changing demand (new SoC, moved deadline).

The registry is the concrete form of the long-parked "persistent flexible-load registry" idea (follow-up to #824) and the substrate for the LLM-ready goal.

## API / contract

New, additive endpoints (sketch — exact paths open):

All endpoints live under the existing **`/api/v1`** namespace (consistent with `/api/v1/last-run`). Transport is REST here; an MQTT intake is a possible follow-on (see Open questions).

- `POST /api/v1/registry/loads` — register a flexible load; returns its id + post-solve outcome.
- `PUT /api/v1/registry/loads/{id}` — update an existing load (new target/deadline/SoC) **or refresh its timeout**.
- `DELETE /api/v1/registry/loads/{id}` — withdraw a load.
- `GET /api/v1/registry/loads` — list active registered loads.
- `GET /api/v1/plan` (or an extension of `GET /api/v1/last-run`) — the current shared plan as structured JSON (the recommendation).

A registered load reuses the **runtime-schema-family** vocabulary rather than inventing a new one — it is essentially a *persisted* runtime deferrable-load demand plus `priority`, `source`, and lifecycle:

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

The same object shape serves **every** consumer — an EV (shown), a heat-pump thermal target, or a generic load (washing machine, dishwasher, pool pump) differ only in field *values*, not structure. Optionally a demand may carry `"template": "<name>"` instead of inline fields, referencing an EMHASS-stored profile.

- Demand fields align with `param_definitions.json` / `runtime_params.json` (the runtime-schema-family; `runtime_params.json` shipped as #915).
- Plan output reuses the plan-output schema (`docs/plan_output_schema.md`, #835) and is versioned by `EMHASS_SCHEMA_VERSION`.
- Load-`priority` semantics depend on a load-priority MILP capability that EMHASS does **not** have today (no inter-load ranking exists). That is proposed as a **sibling RFC**, not folded in here.

## Threat model

Per the #808 maintainer comment (code-injection focus). The new surface introduced here is **persistence**:

- **No pickle / no arbitrary deserialization.** The registry is persisted as **JSON**, validated on load by hand-rolled checks (no schema-validator dependency, consistent with the openapi generator). A malformed or unexpected file is rejected, not executed.
- **No path-traversal.** Writes are confined to the existing `data_path` (the same directory already used for `opt_res_latest.csv`). Load `id`s are server-generated/validated and are **never** used to construct filesystem paths.
- **No shell-out, no DB, no `eval`.** Registry mutations are pure data validated against the demand schema.
- **Corruption-safe writes.** Single writer (the serving process); atomic write via temp-file + rename.
- The API accepts JSON validated against a fixed shape — the same injection-risk class as the existing `/action/*` runtime-params intake. **But persistence widens the *blast radius*:** a bad demand persists across every solve until its `expires_at`, whereas a stateless POST affects one solve only. The mandatory timeout bounds this, and invalid entries are rejected at the API and never persisted.

## Backward compatibility

- **Fully opt-in.** With no registered loads, the solve is functionally identical to today's behaviour; the registry contributes nothing to the optimization. Existing `/action/*`, configuration, and HA publish paths are unchanged.
- **Stateless callers keep working.** A caller that ignores the registry and POSTs the full problem (as today) is unaffected — the registry is an *additional* way to drive EMHASS, not a replacement.
- **No new hard dependency** (stdlib JSON persistence; no new runtime requirement).
- Default config still works unchanged.

## Open questions

- **Recurrence & seasonal enablement** — every entry now carries a mandatory `expires_at` (decided above). What remains open is the *recurrence* model for standing loads: auto-refresh cadence, and calendar/seasonal enablement (e.g. a pool pump active only in summer) — explicit re-`PUT` vs a declared schedule.
- **MQTT intake** — should demands also be submittable via MQTT (devices / HA publish to a topic) in addition to REST/v1? The primitive is transport-agnostic; recommendation is a **separate follow-on RFC** for an MQTT transport adapter rather than expanding this one.
- **Template store** — how stored load templates (reusable profiles referenced by `template`) are defined, versioned, and managed; possibly a follow-on RFC rather than part of this one.
- **Priority semantics**: strict ordering vs weighted soft-penalty — and confirm this lands as a **sibling RFC** (load-priority MILP) rather than here.
- **Persistence location & concurrency** under multi-process / HA-addon deployments (single-writer assumption, lock strategy).
- **Identity / authorization** — EMHASS's API is typically local and unauthenticated. With multiple sources registering, should a `source` own its entries (preventing cross-source overwrite/withdraw, accidental or malicious)? Likely simple per-source namespacing or a token; TBD.
- **Outcome richness**: how detailed should the per-demand admission result be for v1 (minimal feasibility flag vs deferred/reduced/rejected detail)?
- **Consumer adapters are separate artifacts.** Each consumer (evcc/EV first as the cleanest case — precise demand, actuation and feedback; then heat-pump/thermal; then generic loads) is specified outside this RFC: a public usage example plus that consumer's own (often private) glue. This RFC stays consumer-agnostic — it neither mandates nor depends on the evcc/evopt contract, nor on any device actuation protocol.
- **Minimal first slice**: smallest reviewable PR that lands the registry opt-in without the priority feature (single-demand registry + full re-solve + JSON persistence), to validate the direction before the larger surface.
