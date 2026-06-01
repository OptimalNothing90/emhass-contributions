# Contributions-repo digest — what's already conceived re: EMHASS OpenAPI / runtime schemas / EV-EVCC

- **Date:** 2026-05-31
- **Method:** read-only digest of `emhass-contributions` (NOT the `upstream/` submodule)
- **Scope:** surface already-decided work so the EMHASS↔evcc conception doesn't re-derive it; verify EV-flexible-load (#824) artifact status
- **Status:** COMPLETE (one of three verification streams)

---

## 1. AM-1 openapi (planned generator)

Sources: `docs/superpowers/specs/2026-05-29-am-1-design.md` + `plans/2026-05-29-am-1.md`.

**Mechanism:** stdlib-only `scripts/generate_openapi.py` (no pydantic/apispec/jsonschema). Imports `emhass.web_server`, reads `app.url_map` as authoritative route set, pairs each route with a curated schema, skip-lists HTML/UI routes, `raise SystemExit` on any route neither curated nor skipped. Output: `src/emhass/static/openapi.json` (OpenAPI 3.1, `info.version = EMHASS_SCHEMA_VERSION`). Drift guarded by `tests/test_openapi.py` on existing `python-test.yml`.

**Endpoints covered (curated):** `GET /get-config`, `GET /get-config/defaults`, `POST /set-config`, `POST /get-json`, `POST /action/{action_name}`, `GET /api/v1/last-run`, `GET /healthz`.

**Schema sources:** config req/res = `components.schemas.Config` from `param_definitions.json` (SoT; `default` only from param_def, array.* → `items.default`). `last-run`/`healthz` responses inlined as components from `docs/api/v1/last-run.schema.json` + `docs/api/healthz.schema.json`.

**Exclusions:** HTML/UI/setup routes `/`, `/index`, `/template`, `/configuration` skip-listed. Secrets out of contract (setup-time). No new dependency, no served `/openapi.json` route, no structured plan-output JSON Schema.

**/action handling — IMPORTANT:** the planned openapi does **NOT** model a structured `/action/dayahead-optim` request+response. It documents only the **generic** `POST /action/{action_name}`: request body `additionalProperties: true` stub; `201` response `{type: object}` with an `externalDocs` link to `docs/plan_output_schema.md`. Per-action structured request payloads (incl. dayahead-optim/MPC bodies) deferred to **AM-1b**, blocked on AC-2b/AC-2c. AM-1 sequenced after AC-4 (`/healthz`, PR #914) merges.

## 2. Runtime schema family

Source: `audits/2026-05-29-runtime-schema-family.md`. Machine-readable surface splits into **4 files**: `param_definitions.json` (config/startup form schema; GUI + AM-1 config endpoints), `runtime_params.json` (runtime INPUT optimization knobs — AC-2b, PR #915), `runtime_output.json` (runtime OUTPUT/publish routing — AC-2c), `docs/api/*.schema.json` (response schemas: last-run/healthz). `treat_runtimeparams` keys bucketed: A = 10 runtime-only optimization knobs → runtime_params; B = output/publish routing → runtime_output; C = runtime overrides of existing config params; D = per-call data payloads + ML args → AM-1b `/action`; E = 7-8 config-defaults-only keys → AM-7; F = secrets (never schematized); G = legacy aliases.

## 3. Plan-output schema (EMHASS optimization output)

Source: `audits/2026-04-28-plan-output.md` (feeds AC-1 / `docs/plan_output_schema.md`, PR #835, `EMHASS_SCHEMA_VERSION="1.0"`). From the 5 `_publish_*` helpers in `command_line.py`. **11 fixed columns + 4 variable groups:**

- `P_Load` (W, +=consumption), `P_PV` (W), `P_PV_curtailment` (W, gated compute_curtailment), `P_hybrid_inverter` (W, gated inverter_is_hybrid)
- `P_deferrable{k}` (W) — per-load group
- `predicted_temp_heater{k}` (°C), `heating_demand_heater{k}` (kWh) — thermal groups
- `P_batt` (W, gated set_use_battery), `SOC_opt` (**fraction 0..1 in CSV but ×100 in HA** — scaling trap)
- `P_grid` (W), `cost_fun_<name>` (€, multi-col), `optim_status` (text), `unit_load_cost` (€/kWh), `unit_prod_price` (€/kWh)

Sign conventions for `P_grid`/`P_batt`/`P_PV`/curtailment/hybrid/heater flagged `[OPEN]` (for maintainer confirmation).

## 4. EV / EVCC / flexible-load artifacts

**No concrete design artifact (no RFC, no prototype, no spec) for the EV-flexible-load / persistent-load registry.** `rfcs/` holds only `README.md`; `prototypes/` is an unrelated feature-flags scaffold.

- `board/items.json` **DISC-824** (status **In Progress**) — only place the flexible-load idea is recorded: body notes "Track 2 — Persistent flexible loads RFC (not yet on board)… RFC in preparation, will be discussed with David and sokorn before any code." → **memory-only / not-yet-authored**.
- `docs/superpowers/specs/2026-05-10-doc-cookbook-design.md` (+ plan, PR #836) — EV-EVCC recipes **explicitly deferred** pending `evcc-io#29815`; EV cookbook ships as a stub cross-linking #29815.
- `docs/superpowers/specs/2026-05-07-emhass-cross-repo-flow-design.md:248` — design-doc prose references a candidate `EV-1 | EV-EVCC | Persistent flexible-load registry | P0 | unblocks #824 corridor` (not a live card).
- `audits/2026-04-28-plan-output.md` + `plans/2026-05-10-ac-1.md` — name the "Node-RED EVCC adapter" as a downstream consumer motivating schema/version work.
- `docs/superpowers/specs/2026-05-28-i873-design.md` — deferrable-load mis-planning bugfix, tagged "EV-EVCC adjacent (deferrable scheduling is the EV-charging substrate)"; a bugfix, not coupling work.
- `AGENTS.md`, `board/extend.py`, `plans/2026-04-30-ag-7-agents-md.md`, `board/design.md` — reiterate the **#789 scope guard**: EMHASS = MILP optimiser; EVCC/OCPP/vehicle APIs/charger modulation OUT of core, belong in glue layer.

## 5. Board — EV/EVCC/adapter cards

| ID | Title | Status | Phase/Pri |
|----|-------|--------|-----------|
| `DISC-824` | Discussion #824: EV use-cases follow-up to #789 | In Progress | P1 / Phase 1 |
| `EV-9` | NR/MQTT/EVCC simplified setup guide | Ideas | P0 / Phase 4 |
| `CE-7` | GUI EV-section (EV as deferrable load, UX only, no coupling-code) | Ideas | P2 / Phase 5 |
| `AM-4` | Adapter-Modul-Layer (extract HA glue → `src/emhass/adapters/`) | Ideas | P2 / Phase 5 |

No card models an EMHASS↔EVCC coordination/optimizer-API layer; AM-4 (generic adapter extraction, HA-focused, gated on AM-3) is closest.

## GAPS

No repo artifact captures an **EMHASS↔EVCC coordination layer**: the persistent flexible-load registry exists only as a *promised* RFC inside the DISC-824 card body; the EVCC integration contract (drop-in `OPTIMIZER_URI` vs official outbound-hook) is parked on external `evcc-io#29815`. Nothing specs how AM-1's generic `/action/{action_name}` openapi or runtime_params/runtime_output map to an EVCC optimizer-API request/response. AM-1b (structured `/action/dayahead-optim` payload) is the nearest enabling piece — unstarted, blocked on AC-2b/AC-2c.

## Note on the #789 scope guard (decision-relevant)

The repo repeatedly draws the line: **EMHASS core = MILP optimiser; charger modulation / vehicle APIs / EVCC = glue layer, out of core.** A coordination-layer concept must decide where it sits relative to this guard — an EMHASS-side optimizer-API extension (AM-1b-style) stays inside the guard; charger-modulation/control-loop logic does NOT belong in EMHASS core.
