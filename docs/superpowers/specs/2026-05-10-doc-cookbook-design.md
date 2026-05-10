# DOC-cookbook — docs/cookbook/ folder + recipe template — Design

**Date:** 2026-05-10
**Card:** `DOC-cookbook` (board/items.json)
**Issue / Discussion:** [Discussion #824](https://github.com/davidusb-geek/emhass/discussions/824) (David approved 2026-04-28)
**Audit source:** None — reasoning carried by Discussion #824
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Branch:** `docs/doc-cookbook`
**Effort:** S
**Phase / Priority:** Phase 1.5 / P1
**Goal-fit:** (empty — non-goal hygiene, but maintainer-blessed)

## 1. Problem

EMHASS users repeatedly re-derive the same EMHASS-side patterns from scratch — "how do I do EV charging?", "how do I do surplus-only?", "how do I do DHW?", etc. — because `docs/study_cases/` houses long-form walkthroughs and there is no short, focused, copy-pasteable format for an individual pattern. The Discussion #824 thread alone contains a dozen real-world EV patterns from at least six distinct community contributors that cannot land in `study_cases/` without inflating those pages beyond their tutorial scope. Newcomers cannot grep `study_cases/` and pick a recipe; they have to read the narrative and synthesize.

## 2. Goal

Ship the scaffolding for a `docs/cookbook/` section **plus 1-2 seed recipes** drawn from patterns we actually run in production (Node-RED MPC orchestration; battery-aware runtime params). Folder + fixed-template recipe format (Goal / Prerequisites / Config / Snippet / Caveats) + index page + the seed recipes establish the convention so contributors see worked examples, not an empty section. Seeds are intentionally **EVCC-neutral and HA-neutral** — EVCC-specific recipes wait on EVCC Discussion #29815 (Path A vs B Optimizer-API-Agnostik decision, currently pending EVCC-maintainer reply per `project_evcc_sponsor_and_29815`); HA-specific snippets wait on community contributors who run that stack. Cookbook still grows by community contribution; the seed recipes prove the section is alive on day one.

## 3. Decisions

| # | Decision | Source |
|---|----------|--------|
| D1 | Recipe style is **scikit-learn / pandas Cookbook**: short, focused, standalone. Target ≤ 200 lines per recipe. NOT long-form walkthrough (that's `study_cases/`). | Diátaxis convention; pandas/scikit precedent; Item-Body framing |
| D2 | David's Discussion #824 phrasing "complete walkthroughs on a cookbook section" is read as "**standalone-readable** (each recipe complete in itself)", not "long-form". Acknowledged in PR description; reversible if maintainer corrects in review (template extends, recipes can grow). | Discussion #824; per `feedback_source_resolve_first` — source-ambiguous, picking the convention-aligned reading |
| D3 | Fixed template sections, in this order: **Goal / Prerequisites / Config / Snippet / Caveats**. No deviation per recipe. Consumers scan a known structure. | Item body, Diátaxis how-to template |
| D4 | **Scaffold + 2 seed recipes**, both EVCC-neutral / HA-neutral: (a) "MPC orchestration via Node-RED" — generic inject → function → http-request pattern to drive `/action/naive-mpc-optim`, no EVCC, no HA. (b) "Battery-aware runtime params" — feeding battery SOC / current power back as runtime params per MPC call (user runs battery in EMHASS optim per `project_user_has_battery`). Both authentic, both source-verifiable against `optimization.py` / `utils.py`. Reasoning: empty scaffolds are graveyards — seed at least 2 worked examples so the section reads as alive at launch. | counter-empty-section risk; honest authentic stack |
| D4a | **EVCC-flavored EV recipes are deferred** pending Discussion #29815 (EVCC Optimizer-API-Agnostik). Until EVCC-maintainer reply on Path A (drop-in OPTIMIZER_URI) vs Path B (official outbound hook), writing EVCC-snippet recipes would preempt that decision. Cookbook EV category in index gets "Contributions welcome — EVCC integration architecture under discussion in evcc-io#29815" stub. | `project_evcc_sponsor_and_29815`; avoid preempting upstream architecture decision |
| D4b | **HA-flavored recipes** invited from community contributors. Index stub mentions Discussion #824 as seed material. We do not author HA snippets (no HA at home, can't authentically test). | honest authentic scope |
| D4c | **Private-repo content stays private.** `loxonesmarthome` is NEVER referenced in public docs. Node-RED recipes derive *generic* patterns from our stack — flow shapes, function-node logic, http-request configuration — but never copy verbatim flow JSON, never include private endpoints, sensor names, or credentials. | privacy discipline |
| D5 | `index.md` lists planned recipe categories as section headers (EV / DHW / Heat Pump / Battery / Forecast / Tariff / Transport — Node-RED + Loxone + HA + EVCC). All sections empty in this PR. Each section has a "Contributions welcome — open a PR adding `<category>_<pattern>.md` based on `_template.md`" line. Cross-references seed material in Discussion #824 (EV), Discussion #823 (good practices), etc. so contributors know where to draw from. | scikit-learn examples-gallery precedent; community-contribution invitation |
| D6 | Cross-link from `study_cases/ev.md` to `cookbook/index.md` is **deferred** to the first EV-recipe PR (when there's actually something on the other end of the link). This PR adds the empty section; ev.md stays untouched. | scope discipline; avoid pointing to empty page |
| D7 | Sphinx toctree wiring: `cookbook/index` becomes a top-level entry in `docs/index.md` toctree, sibling to `study_cases/index`. Not nested under study_cases. The two sections are peers, not parent-child. | Sphinx convention; David's quote treats them as peers |
| D8 | No new code, no constants, no Python changes. Pure docs PR. | Effort=S; doc-only by item nature |
| D9 | Future recipe PRs MUST source-verify their EMHASS-config sections against `src/emhass/optimization.py` and `src/emhass/utils.py`, MUST credit Discussion-thread contributors when patterns come from there, MUST mark untested transport variants explicitly. Stated in `_template.md` so contributors see the rule. | `feedback_source_resolve_first`; community attribution norm |

## 4. Files touched

- **NEW:** `docs/cookbook/index.md` — landing page with category sections; Transport/integration category populated with 2 recipe links; other categories show "contributions welcome" stubs
- **NEW:** `docs/cookbook/_template.md` — fixed-section template, `:orphan:`, contributor-rule note per D9
- **NEW:** `docs/cookbook/nodered_mpc_orchestration.md` — seed recipe (a)
- **NEW:** `docs/cookbook/battery_aware_runtime_params.md` — seed recipe (b)
- **MOD:** `docs/index.md` — add `cookbook/index` to top-level toctree as peer of `study_cases/index`

NOT touched in this PR:
- `docs/study_cases/ev.md` — cross-link deferred per D6 (no EV recipe yet to link to)
- No EVCC-specific recipes — per D4a, pending Discussion #29815

## 5. Concrete edits

| File | Edit | Detail |
|------|------|--------|
| `docs/cookbook/index.md` | create | H1 "Cookbook". Intro paragraph: purpose (scikit/pandas-style short standalone recipes), Diátaxis positioning (How-to-guide quadrant; study_cases stays narrative). How-to-contribute paragraph: copy `_template.md`, fill sections, link from this index, open PR. Category sections: **EV charging** ("Contributions welcome — EVCC integration architecture under discussion in evcc-io#29815; see emhass#824 for HA-flavored community patterns"), **DHW**, **Heat pump**, **Battery** ("Contributions welcome — see #823 for good practices"), **Forecast**, **Tariff**, **Transport / integration** (populated: links to nodered_mpc_orchestration.md and battery_aware_runtime_params.md; invite for HA / EVCC / AppDaemon / Loxone variants). Target ≤ 120 lines. |
| `docs/cookbook/_template.md` | create | Literal copy-pasteable template, `:orphan:` at top to suppress toctree warning. Top comment: "Copy this file, rename, fill sections, link from index.md". 5 fixed sections with one-line guidance: "Goal: one sentence — what does this recipe achieve?"; "Prerequisites: what must be in place (EMHASS version, config flags, runtime env, transport stack)"; "Config: YAML / JSON snippet, runnable as-is, source-cited per D9"; "Snippet: HA `rest_command` / Node-RED / Python / EVCC API / Loxone — the actual integration code, marked with which stack it was tested against"; "Caveats: known limits, edge cases, when this pattern breaks". Final section: "Credits: discussion handles, line citations, prior art." Includes contributor-rule note: "Patterns must be source-verified against `src/emhass/optimization.py` (D9). Untested transport variants must be marked as such." Target ≤ 60 lines. |
| `docs/cookbook/nodered_mpc_orchestration.md` | create | **Goal:** "Drive EMHASS naive-MPC optimization from Node-RED on any cadence, with runtime params computed per call." **Prereqs:** EMHASS reachable via HTTP, Node-RED 3+ with `http request` + `function` nodes, deferrable / battery / thermal configured in EMHASS as needed. **Config:** transport-agnostic YAML extract for static EMHASS config (deferrables + battery skeleton) — source-cited against `utils.py:treat_runtimeparams` per D9. **Snippet:** generic Node-RED flow shape (described in prose + a small flow JSON skeleton): `inject` cron (5-min default) → `function` node assembling `runtime_params` dict (only fields the flow recomputes per tick: `def_total_hours`, `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load`, `prod_price_forecast`, `load_cost_forecast`) → `http request` POST `http://<emhass-host>:5000/action/naive-mpc-optim` with the runtime_params as body → optional `debug` node on the result. **Caveats:** EMHASS timeout (long runs > 120s), Node-RED `function` node memory between ticks (use `flow.set` for state), error handling when EMHASS returns 500, runtime_params field names sensitive to EMHASS version. **Credits:** prior art in `docs/study_cases/mpc.md` (long-form walkthrough). No private flow JSON copied — pattern only. Target ≤ 170 lines. |
| `docs/cookbook/battery_aware_runtime_params.md` | create | **Goal:** "Feed live battery SOC + power back into EMHASS naive-MPC so the optimizer sees the current battery state on each call." **Prereqs:** Battery configured in EMHASS (`set_use_battery: true`, capacity, efficiency, SOC bounds — source-cited against optimization.py battery constraints per D9), battery SOC + power sensors reachable from Node-RED (any source: Modbus, MQTT, HA bridge, manufacturer API). **Config:** YAML extract showing `set_use_battery: true` plus `SOCtarget`, `SOCmin`, `SOCmax`, `Pd_max`, `Pc_max`, `eta_disch`, `eta_ch` with brief one-line meanings — sourced from `config_defaults.json` keys. **Snippet:** Node-RED flow that reads battery sensors (generic source-agnostic example), normalizes SOC to EMHASS expected range (fraction 0..1 — cite the `SOC_opt` HA-scaling trap from `docs/plan_output_schema.md` once AC-1 PR #835 merges; until then cite optimization.py inline), injects `soc_init` into runtime_params on every MPC call. **Caveats:** SOC unit mismatch is the #1 consumer bug (fraction in EMHASS, percent in many sensor sources); `soc_init` field name versus `SOCtarget`; what happens if battery sensor is stale (Node-RED `delay` + `last_value` pattern); EMHASS doesn't enforce safety bounds — battery hardware should still have its own BMS limits. **Credits:** discovered while building PR #835 plan-output schema doc (SOC scaling). Target ≤ 170 lines. |
| `docs/index.md` | mod | Locate the `{toctree}` directive that lists `study_cases/index`. Insert `cookbook/index` immediately after (peers per D7). Single-line addition. |

## 6. Test strategy

Documentation PR with 2 seed recipes. Source-trace verification required for both seeds per D9.

- **Source-trace verification (D9):** for each seed recipe, before writing Config / Snippet sections:
  - `nodered_mpc_orchestration.md` — verify `utils.py:treat_runtimeparams` accepts each runtime_params field referenced in the snippet (`def_total_hours`, `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load`, `prod_price_forecast`, `load_cost_forecast`). Cite line numbers in `<!-- source: utils.py:NNN -->` HTML comments above the relevant section.
  - `battery_aware_runtime_params.md` — verify battery constraint variables in `optimization.py` (`set_use_battery` gate, `SOC` upper/lower bounds, charge/discharge efficiency, `soc_init` runtime override). Cite line numbers. Confirm SOC unit convention (fraction 0..1) against the same source AC-1 / PR #835 documented.
- **Sphinx build:** `cd docs && ./make.bat html`. Must succeed without warnings naming any new file. `_template.md` is `:orphan:`.
- **Render check:** open `_build/html/cookbook/index.html`, `nodered_mpc_orchestration.html`, `battery_aware_runtime_params.html`. Verify category sections render, recipe links resolve, code blocks highlight.
- **Toctree check:** `cookbook/index` appears in `docs/index.html` navigation alongside `study_cases/index`.
- **Privacy lint (D4c):** grep both recipe files for any private endpoint, sensor name, or path. Must return zero matches against `loxone`, internal IP ranges, or repo-private identifiers. Manual eyeball; if patterns leak, redact and re-grep.
- **No automated test added.** Per AC-1 precedent: docs PRs don't carry unit tests.

## 7. Acceptance criteria

1. `docs/cookbook/` folder exists with `index.md`, `_template.md`, `nodered_mpc_orchestration.md`, `battery_aware_runtime_params.md`.
2. `index.md` renders all planned category sections (EV, DHW, Heat Pump, Battery, Forecast, Tariff, Transport / integration). Transport / integration section links to the 2 seed recipes; other sections show "contributions welcome" stubs with seed-material references (#789 / #823 / #824, evcc-io#29815).
3. `_template.md` is copy-pasteable, marked `:orphan:`, includes the contributor-rule note from D9.
4. Each seed recipe ≤ 200 lines, follows the fixed template, ends with `## Credits`, contains `<!-- source: ... -->` HTML comments above Config and Snippet code blocks per D9.
5. Privacy check (D4c): grep of both recipe files returns zero matches for private endpoints, internal IPs, Loxone identifiers, or any `loxonesmarthome` repo strings.
6. `docs/index.md` toctree includes `cookbook/index` as peer of `study_cases/index`.
7. `study_cases/ev.md` is **not** modified (cross-link deferred to first EV-recipe PR per D6).
8. Sphinx build succeeds; no warnings name any new file.
9. PR description:
   - acknowledges the D2 ambiguity (David's "complete walkthroughs" phrasing) and invites maintainer to flip the recipe-length convention if the current scikit/pandas-style reading misses his intent.
   - explains the seed choice: Node-RED MPC orchestration + battery-aware runtime params, chosen because (a) the author runs both in production, (b) both are EVCC-neutral and HA-neutral so they don't preempt EVCC Discussion #29815 or burden HA-less authors.
   - explicitly invites community contributions for EV-EVCC (pending #29815), HA `rest_command`, AppDaemon, Loxone-direct, etc.
   - confirms scope: 2 seed recipes + scaffold; further recipes in follow-up PRs.

## 8. Out of scope

- **EVCC-flavored recipes** — deferred pending Discussion #29815 outcome (Path A vs B). Cookbook EV category stays a stub with the #29815 cross-link until then.
- **HA `rest_command` / AppDaemon recipes** — author doesn't run HA; invited from community.
- **Loxone-direct recipes** — possible future follow-up, generic patterns only (private flow JSON never copied per D4c).
- **EV-specific recipes** (daily-commute, surplus-only, multi-day window, calendar-driven, negative-price-aware) — all wait on either EVCC #29815 resolution or community-contributed HA versions.
- **Other non-EV recipes** (DHW, heat pump, dedicated battery scheduling, forecast, tariff) — placeholders in index; recipes accrue over time.
- Cross-link from `study_cases/ev.md` to cookbook — deferred until first EV recipe lands.
- Migrating `study_cases/ev.md` content into cookbook recipes — EV-9 / future PR.
- Renaming or restructuring `study_cases/` — peer-coexistence per D7.
- Correcting `study_cases/ev.md` ("known limits" admonition) — separate concern, separate PR.
- Diátaxis-purity audit of existing docs — separate concern.
- Automated link-checker / linting tooling — premature; defer until cookbook has more entries.
- Private-repo content (`loxonesmarthome`) — never copied into public docs per D4c.

## 9. References

- Discussion: [emhass#824](https://github.com/davidusb-geek/emhass/discussions/824)
- Sibling discussion: [emhass#823](https://github.com/davidusb-geek/emhass/discussions/823) (good-practices crowdsourcing — feeds non-EV recipes later)
- Sibling discussion: [emhass#789](https://github.com/davidusb-geek/emhass/discussions/789) (EMHASS = MILP core; cookbook lives in glue layer per maintainer scope-corridor)
- Sibling discussion: [emhass#820](https://github.com/davidusb-geek/emhass/issues/820) (multi-trip EV planner — possible future recipe)
- Board item: `EV-9` (Phase 4, Ideas) — retargeted to cookbook per `EV-9.body`, will land additional EV recipes here
- Convention precedent: pandas Cookbook (`https://pandas.pydata.org/docs/user_guide/cookbook.html`), scikit-learn Examples Gallery
- Convention reference: Diátaxis framework (Procida) — How-to Guide quadrant
- Memory: `feedback_pr_first_for_strategic.md`, `feedback_branch_naming.md`, `feedback_source_resolve_first.md`, `project_user_has_battery.md`, `project_evcc_sponsor_and_29815.md`
- Primary source for seed-recipe + future recipe-PR verification (per D9): `src/emhass/optimization.py`, `src/emhass/utils.py` (`treat_runtimeparams`), `src/emhass/data/config_defaults.json`
- Existing context: `docs/study_cases/ev.md` (long-form walkthrough — self-flagged "Early-draft page"; do NOT trust as primary source per D9), `docs/study_cases/mpc.md` (long-form MPC walkthrough — prior art for nodered_mpc_orchestration recipe)
- EVCC architecture under discussion: [evcc-io/evcc#29815](https://github.com/evcc-io/evcc/discussions/29815) — gates EV-EVCC recipes
- AC-1 / PR #835 (plan-output schema doc + `EMHASS_SCHEMA_VERSION`) — battery-aware recipe cross-references the SOC scaling discovery from this work
