# flexd — generic demand-registry sidecar for EMHASS (MVP design)

**Date:** 2026-07-05
**Status:** Design approved in session (sections 1–4), pre-implementation
**Basis:** RFC 0001 (S1 external-sidecar pivot), `docs/plans/2026-07-05-evcc-emhass-integration-plan.md` (WS2),
EMHASS `master@f11d8dea` (`GET /api/v1/plan` #995, `def_current_power` #982, `/healthz` #914)
**Working name:** `flexd` (flexible-demand daemon). Neutral, no "emhass" in the name; final name decided
at the ally call (see WS2 placement sequence).

## Goal

A small external service that is the glue between EMHASS and everything else in the house.
Consumers (Loxone, Home Assistant, ioBroker, Node-RED, LLM agents) register flexible demands
(EV session, dishwasher, washing machine, pool pump, thermal targets); flexd folds all active
demands into one EMHASS optimization per MPC cycle and republishes the resulting plan in forms
each consumer can trivially digest. **EMHASS remains the only solver. flexd never optimizes and
never actuates** — consumers read setpoints and drive their own hardware.

Priorities (user decision 2026-07-05): Loxone first (author's household), Home Assistant next
(allies), ioBroker documented. Easy setup is a core deliverable, not an afterthought: one
docker-compose bundle including EMHASS itself, one config file, copy-paste client guides,
agent-usable OpenAPI.

## Decisions log (session 2026-07-05)

| Decision | Choice |
|---|---|
| Architecture | A: one process, one container, six internal modules (asyncio) |
| Loxone path | Both: JSON REST + plain-value Simple-API + documented Node-RED flow |
| MQTT | Full bidirectional in MVP (intake + publish), lifecycle via idempotent upsert + mandatory `expires_at` |
| Agent capability | Clean OpenAPI in MVP; dedicated MCP server is Phase 2 (thin wrapper) |
| Packaging | docker-compose bundle: flexd + EMHASS + Mosquitto (broker optional via profile) |
| Stack | Python 3.12, FastAPI + pydantic, aiomqtt; JSON persistence, no DB, no pickle |
| Location | `prototypes/flexd/` in emhass-contributions, pre-placement; moves to community org repo after ally call |

## 1. Architecture

```
Consumers                          flexd (one container)                    EMHASS (unchanged, the solver)
─────────                          ────────────────────────────            ────────────────────────────────
Loxone ── HTTP simple ──┐          ┌──────────────────────────┐
HA/ioBroker ── MQTT ────┼──▶ intake│ transports               │
Node-RED ── REST JSON ──┘          │  ├─ rest_api   (FastAPI) │
LLM agent ── REST/OpenAPI ─▶       │  ├─ simple_api (plain)   │
                                   │  └─ mqtt_bridge (aiomqtt)│
                                   ├──────────────────────────┤
                                   │ registry  (JSON, atomic) │
                                   ├──────────────────────────┤
                                   │ scheduler (MPC cycle)    │
                                   │   └─ aggregator          │──POST /action/naive-mpc-optim──▶ MILP
                                   │   └─ emhass_driver       │◀─GET /api/v1/plan────────────────┘
                                   ├──────────────────────────┤
                                   │ plan_view (per-demand    │──publish──▶ MQTT topics
                                   │  setpoints from plan)    │◀──poll──── Loxone / anyone
                                   └──────────────────────────┘
```

Six modules, one asyncio process:

| Module | Purpose | Depends on |
|---|---|---|
| `registry` | Demand CRUD + `expires_at` lifecycle; JSON persistence, atomic tmp+rename, single writer | — |
| `aggregator` | Active demands → one runtimeparams payload (deferrable arrays) | registry |
| `emhass_driver` | POST optim, GET `/api/v1/plan`, `/healthz` check, schema-version guard | aggregator |
| `plan_view` | Plan → per demand: current setpoint (W), on/off, next window, satisfied energy | emhass_driver |
| `transports` | REST (JSON + OpenAPI), Simple-API (bare values), MQTT (intake + publish) | registry, plan_view |
| `scheduler` | Cycle loop (interval = EMHASS timestep), debounced immediate re-solve on demand change | all |

Module boundaries are drawn so a later split into core+adapter containers (approach B) is a
refactor, not a rewrite. Hard rules: no pickle, no eval, demand ids never used to build
filesystem paths, single writer to the registry file.

## 2. Data model and API surface

### Demand object (pydantic-validated; RFC 0001 vocabulary)

```jsonc
{
  "id": "server-generated",          // or client-supplied, [a-z0-9-]{1,64}, never a path
  "source": "loxone",                // namespace: only the owning source may update/delete
  "type": "ev | thermal | generic",
  "flexibility": "shiftable | committed | hybrid",
  "energy_target_wh": 1200,
  "nominal_power_w": 2000,
  "p_min_w": 0,                      // optional
  "window_start": "ISO8601",
  "deadline": "ISO8601",
  "expires_at": "ISO8601",           // MANDATORY — stale demands age out
  "priority": 1,                     // stored; NOT passed to the MILP in MVP (EMHASS has no priority yet)
  "current_power_w": 0               // optional live value → def_current_power pin
}
```

### Identity, ownership, and id rules (MVP contract)

- **`id` is globally unique** across all sources. The registry key is `id` alone; `source` is an
  ownership attribute. A client-supplied `id` that already exists under a different `source` is
  rejected (REST 409; MQTT error event). This keeps the Simple-API and plan topics (`{id}` only)
  collision-free.
- **Ownership is declarative in the MVP.** flexd runs on a trusted LAN; a caller's `source` claim
  is not authenticated. Update/delete is refused when the claimed `source` differs from the
  stored one — a guard against accidents, not against malice. Real per-source tokens are Phase 3;
  the guides say so explicitly.
- **Refresh semantics.** Every demand stores `ttl_s`, derived at registration
  (`expires_at − received_at`, or the `flexd.yaml` default when the Simple-API defaulted it).
  A `refresh` (REST `PUT` without body changes, Simple `/refresh`, MQTT re-`set` with same
  payload) sets `expires_at = now + ttl_s`. A `PUT`/`set` carrying a new `expires_at` overrides
  the TTL and re-derives `ttl_s`.
- **Redundant energy fields.** `energy_target_wh` is authoritative. The Simple-API `hours` param
  is a convenience: when both `energy_wh` and `hours` are given, `energy_wh` wins and `hours` is
  ignored; `hours` alone is converted via `power_w` (`energy = hours × power`). Mixed
  inconsistent values are not an error — the precedence rule is the contract.

### REST (`/api/v1`, full OpenAPI served at `/openapi.json` + `/docs`)

- `POST /demands` · `PUT /demands/{id}` (update = refresh) · `DELETE /demands/{id}` · `GET /demands`
- `GET /plan` — raw EMHASS plan passed through (EMHASS schema + `flexd_meta` block)
- `GET /plan/demands/{id}` — per-demand view: `{setpoint_w, on, window, satisfied_wh, status}`
- `GET /healthz` — own health + cascaded EMHASS health
- `POST /cycle` — manual re-solve trigger

### Simple-API (Loxone Virtual I/O; no JSON anywhere)

- `GET /simple/demands/{id}/setpoint` → `2000` (bare number, `text/plain`)
- `GET /simple/demands/{id}/on` → `1|0`
- `POST /simple/demands/register?source=loxone&id=spuelmaschine&energy_wh=1200&power_w=2000&hours=4&deadline_in_h=8`
  — query params only, generous defaults (e.g. `expires_at` defaults to deadline + 1 h)
- `POST /simple/demands/{id}/done` (= withdraw/DELETE) · `POST /simple/demands/{id}/refresh` (= bump `expires_at`)
- `GET /simple/status` → `ok|stale|no-run|down` (feeds a Loxone watchdog block; `down` =
  EMHASS unreachable — the one state Simple-API adds over `plan/state`)

### MQTT (bidirectional, base topic `flexd/`)

| Direction | Topic | Payload |
|---|---|---|
| intake | `flexd/demands/{source}/{id}/set` | demand JSON; partial update = refresh (idempotent upsert) |
| intake | `flexd/demands/{source}/{id}/delete` | empty |
| publish | `flexd/plan/state` | `ok|stale|no-run` + `generated_at` (retained) |
| publish | `flexd/plan/demands/{id}/setpoint` | number (retained) |
| publish | `flexd/plan/demands/{id}/on` | `1|0` (retained) |
| publish | `flexd/plan/full` | raw plan JSON (retained, single topic — no topic spam) |
| publish | `flexd/availability` | `online|offline` (LWT) |
| publish | `flexd/demands/{source}/{id}/error` | validation error events |

MQTT lifecycle concern (register-over-MQTT is fiddly) is defused by: `set` = idempotent
upsert+refresh, retained result topics, and the mandatory `expires_at` — a dead publisher's
demand simply ages out. **Retained-topic cleanup:** when a demand is withdrawn or expires, flexd
publishes empty retained payloads to its `setpoint`/`on` topics to clear them — no ghost
setpoints after removal. Home Assistant MQTT Discovery config topics are Phase 2; the topic
layout above is already cut to make that additive. ioBroker consumes the same topics via its
mqtt adapter.

## 3. Cycle, error paths, fail-safe

### MPC cycle (scheduler loop)

1. Tick (interval = EMHASS `optimization_time_step`, default 30 min) **or** demand change
   (debounced 10 s) **or** `POST /cycle`.
2. `registry.sweep()` — drop expired demands (event to log + MQTT).
3. No active demands → skip cycle, `plan/state = no-run`. EMHASS may keep running for its
   static config; flexd does not interfere.
4. `aggregator`: demands → `number_of_deferrable_loads`, nominal powers, `def_total_hours`,
   start/end timesteps, `def_current_power` — deterministic slot assignment (sorted by `id`);
   the demand↔slot mapping table is stored alongside the plan.
   **Deferrable ownership contract:** when flexd calls EMHASS, its runtimeparams fully specify
   the deferrable arrays — EMHASS's statically-configured deferrable loads are overridden for
   that run (runtimeparams mechanics, not a flexd choice). Users with existing static loads
   migrate them into `flexd.yaml` as **standing demands** (below); the guides walk through
   this. Rule of thumb in docs: *either* EMHASS owns its deferrables *or* flexd does — not both.

   **Standing demands (MVP shape — deliberately minimal daily pattern, not full recurrence):**
   a `flexd.yaml` block per recurring load:

   ```yaml
   standing_demands:
     - id: waterheater          # same id rules as dynamic demands
       type: generic
       nominal_power_w: 3000
       daily_hours: 5           # or daily_energy_wh; same precedence rule as the Simple-API
       window: "06:00-22:00"    # local time (flexd.yaml timezone), converted to UTC per day
   ```

   Materialization each cycle — standing *definitions* live in config, never in the registry;
   the materializer **upserts an ordinary registry demand** from each definition, so the
   registry contract holds unmodified:

   - If *now* is inside today's window: upsert demand `id` with `source: config`, concrete
     `window_start`/`deadline` = today's window, and **`expires_at` = today's window end** —
     the mandatory-`expires_at` rule and the normal expiry sweep apply as-is (no exemption;
     outside the window the instance is simply expired/absent, which is correct: it is
     inactive). Next day, the materializer seeds a fresh instance.
   - Remaining hours = `daily_hours` minus the on-hours already **elapsed** today, read from a
     small per-day ledger (`standing_ledger.json`: per standing id, cumulative on-hours from
     previously *adopted* plans, reset at local midnight; documented assumption: consumers
     follow the plan).
   - Corrections (e.g. the boiler already ran manually) use the same declarative trust as
     everything else in the MVP: send an update claiming `source: config` — structural fields
     still come from YAML on the next reseed, so a correction is a same-day override, not a
     config change.
   - Startup validation: a standing id colliding with an existing dynamic demand of another
     source is a fatal config error (loud, at boot — not a runtime surprise).

   Standing definitions are removed/reseeded on config reload or restart. Weekly/seasonal/
   calendar rules remain Phase 3 — the MVP pattern is exactly "same window, every day".
   **Escape hatch:** `flexd.yaml: extra_runtime_params` — a JSON object merged into every optim
   POST (e.g. `soc_init` source overrides, custom weights). flexd validates it is a dict, passes
   it through untouched, and never overrides its own deferrable keys with it (flexd keys win on
   conflict, conflict logged).
5. `emhass_driver`: POST `naive-mpc-optim` (awaited) → GET `/api/v1/plan`.
6. Response guards: `status == ok`? `emhass_schema_version` known? `generated_at` newer than
   the last accepted plan? Only then does `plan_view` adopt + publish.
7. Every cycle writes `last_cycle.json` (timestamp, payload hash, result status) — debug crumb.

### Error paths (the happy-path classes, explicitly)

| Failure | Behavior |
|---|---|
| EMHASS down / timeout | last valid plan stays published; `plan/state → stale` after 2× cycle interval; Loxone watchdog sees it via `/simple/status` |
| Solve `Infeasible`/`error` | `/api/v1/plan` keeps serving the last valid plan (upstream D4a invariant); flexd marks `stale` + emits `infeasible` event with payload hash; demands stay registered |
| Unknown schema version | plan NOT adopted, `stale`, error log — fail closed rather than mis-map |
| Invalid demand | rejected at intake, never persisted (REST: 400 with pydantic detail; MQTT: event on `.../error`) |
| Corrupt registry file | on load: try `.bak`, else start empty + loud warning — never crash |
| MQTT broker down | REST keeps working (broker is not a hard dependency); reconnect with backoff; LWT handles `availability` |
| flexd restart | registry reloaded from disk; retained topics still stand — consumers notice nothing |
| Clock/DST | everything UTC internally (matching `/api/v1/plan`); deadlines accepted with TZ offset and converted |

### Fail-safe contract for consumers (documented, part of every client guide)

Actuate only on `state=ok` and `on=1`. On `stale`/`offline`/timeout → device falls back to its
safe native mode (EV: evcc `off` or `pv`; dishwasher: just run now). flexd cannot enforce this
(it is recommend-only), but every documented client flow (Loxone blocks, Node-RED flow, HA
blueprint) implements it up front.

## 4. Packaging, setup guide, testing, phases

### Packaging

```
prototypes/flexd/
├─ docker-compose.yml      # 3 services: flexd, emhass, mosquitto (broker optional via profile)
├─ flexd.yaml              # ONE config file: emhass_url, mqtt, timestep, defaults, standing demands,
│                          #   extra_runtime_params — every option commented
├─ Dockerfile              # python:3.12-slim, non-root, HEALTHCHECK → /healthz
├─ src/flexd/              # the six modules
├─ tests/
└─ docs/
```

- `docker compose up -d` = whole system including EMHASS. Existing-EMHASS users: profile flag +
  `emhass_url` pointing at their instance.
- Env-var overrides for every config key (compose-friendly).
- Unraid: compose works today (Compose Manager plugin); native Unraid template is a follow-on.

### Setup guide (core deliverable, not an appendix)

1. README quickstart: 10 minutes from zero to running system, including minimal EMHASS config
   (the ~6 mandatory values; everything else linked to EMHASS docs). Written for non-LLM users.
2. Per-client guides, copy-paste ready: **Loxone** (Virtual Outputs/Inputs step-by-step with
   screenshots, watchdog block), **Home Assistant** (MQTT + rest_command; blueprint in Phase 2),
   **ioBroker** (mqtt adapter), **Node-RED** (importable flow — the author's production variant,
   generalized).
3. Agent guide: OpenAPI URL + three example prompt/curl sequences (register → read plan → withdraw).
4. Every guide ends with the fail-safe section (§3 contract).

### Testing

- **Unit:** registry (lifecycle, atomic write, corruption recovery), aggregator
  (demand→runtimeparams, deterministic slot mapping, standing-demand daily materialization
  incl. plan-based elapsed-hours accounting and DST-day windows), plan_view (plan→setpoints
  incl. `no-run`/`stale`).
- **Contract:** emhass_driver against recorded `/api/v1/plan` fixtures (ok, no-run, schema
  drift) — no live EMHASS needed.
- **Integration:** compose-based E2E in CI against the real EMHASS image — demand in, plan out,
  setpoint correct, expiry sweeps. (The test class that catches happy-path-only PRs.)
- **MQTT:** roundtrip against Mosquitto in a CI container.

### Phases

| Phase | Content |
|---|---|
| **1 (MVP)** | All six modules; REST + Simple + bidirectional MQTT; compose bundle; Loxone + Node-RED guides; unit/contract/E2E tests. Demo-ready for the ally call. |
| 2 | HA MQTT Discovery + blueprint; ioBroker guide verified; MCP server (thin wrapper over REST); Unraid template |
| 3 | Full recurrence/seasonal/calendar rules (beyond the MVP daily standing-demand pattern); demand templates (`dishwasher-eco`); priority pass-through once the EMHASS priority MILP exists (WS3 sibling); per-source auth tokens |

## Out of scope (MVP)

- Any optimization logic in flexd (EMHASS is the solver, permanently).
- Any actuation by flexd (consumers actuate; documented flows only).
- Priority arbitration (stored but inert until EMHASS supports it).
- EV SoC-curve fidelity (that is WS3/N2, an EMHASS change, not a sidecar change).
- Multi-instance / HA-addon deployment concurrency (single writer assumed and enforced).
