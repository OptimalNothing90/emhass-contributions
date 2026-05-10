# DOC-cookbook — Cookbook Scaffold + Node-RED MPC + Battery-Aware Seed Recipes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a new `docs/cookbook/` Sphinx-rendered section in the EMHASS docs tree with a fixed-template (Goal / Prerequisites / Config / Snippet / Caveats), plus two seed recipes documenting EVCC-neutral / HA-neutral patterns: Node-RED MPC orchestration and battery-aware runtime params.

**Architecture:** Pure docs PR. New folder `docs/cookbook/` with `index.md`, `_template.md` (`:orphan:`), and two recipe files. `docs/index.md` toctree gains one entry. Both recipes are source-verified against upstream `src/emhass/utils.py` (`treat_runtimeparams`), `src/emhass/optimization.py` (battery constraints), and `src/emhass/data/config_defaults.json` (canonical key names). Privacy lint (D4c) ensures no `loxonesmarthome` content leaks into public docs.

**Tech Stack:** Sphinx with MyST Markdown, `{toctree}` directives, `:orphan:` directive.

**Spec source:** `../emhass-contributions/docs/superpowers/specs/2026-05-10-doc-cookbook-design.md`
**Audit source:** Discussion [#824](https://github.com/davidusb-geek/emhass/discussions/824) (David approved 2026-04-28); no formal audit doc
**Item context:** Discussion [#823](https://github.com/davidusb-geek/emhass/discussions/823) (good-practices), Discussion [#789](https://github.com/davidusb-geek/emhass/discussions/789) (scope corridor), Discussion [evcc-io#29815](https://github.com/evcc-io/evcc/discussions/29815) (EVCC integration architecture, gates EV-EVCC recipes)

**Canonical EMHASS parameter names** (verified against `config_defaults.json` on 2026-05-11 — re-verify in Task 2):

| Recipe needs | Real name in EMHASS |
|---|---|
| Deferrable nominal power | `nominal_power_of_deferrable_loads` |
| Deferrable operating hours | `operating_hours_of_each_deferrable_load` |
| Deferrable window start | `start_timesteps_of_each_deferrable_load` |
| Deferrable window end | `end_timesteps_of_each_deferrable_load` |
| Battery enable flag | `set_use_battery` |
| Battery target SOC | `battery_target_state_of_charge` |
| Battery min SOC | `battery_minimum_state_of_charge` |
| Battery max SOC | `battery_maximum_state_of_charge` |
| Battery discharge power max | `battery_discharge_power_max` |
| Battery charge power max | `battery_charge_power_max` |
| Battery discharge efficiency | `battery_discharge_efficiency` |
| Battery charge efficiency | `battery_charge_efficiency` |
| Live SOC injection (runtime param) | `soc_init` |
| Load cost forecast (runtime param) | `load_cost_forecast` |
| Production price forecast (runtime param) | `prod_price_forecast` |

Spec referenced earlier shorter names (`SOCtarget`, `Pd_max`, `def_total_hours`, etc.) lifted from `study_cases/ev.md` / Discussion folklore. **Those are wrong.** Use the canonical names above.

---

## Pre-flight (run once before Task 1)

- [ ] **P1: Verify working directory is the fork repo**

Run:
```bash
git rev-parse --show-toplevel
```
Expected: `C:/Users/MauricioSchäpers/claude-code/emhass`.

- [ ] **P2: Verify upstream remote**

Run:
```bash
git remote -v
```
Expected: `origin` → `OptimalNothing90/emhass`, `upstream` → `davidusb-geek/emhass`.

- [ ] **P3: Sync master with upstream**

Run:
```bash
git fetch upstream
git checkout master
git merge --ff-only upstream/master
```
Expected: fast-forward or "Already up to date".

- [ ] **P4: Verify active GitHub account**

Run:
```bash
gh auth status
```
Expected: `OptimalNothing90` active. Switch if not.

- [ ] **P5: Clean tree**

Run:
```bash
git status --short
```
Expected: empty.

---

## Task 1: Create branch `docs/doc-cookbook`

- [ ] **Step 1.1: Create branch**

```bash
git checkout -b docs/doc-cookbook
```

- [ ] **Step 1.2: Verify branch tracks upstream/master**

```bash
git log --oneline -1 HEAD
git log --oneline -1 upstream/master
```
Both SHAs identical.

---

## Task 2: Source-trace verification (D9, mandatory before writing recipes)

**Files:** read-only inspection of `src/emhass/utils.py`, `src/emhass/optimization.py`, `src/emhass/data/config_defaults.json`

- [ ] **Step 2.1: Verify deferrable-load parameter names in config_defaults**

```bash
grep -n "nominal_power_of_deferrable_loads\|operating_hours_of_each_deferrable_load\|start_timesteps_of_each_deferrable_load\|end_timesteps_of_each_deferrable_load" src/emhass/data/config_defaults.json
```
Expected: at least one match for each key.

- [ ] **Step 2.2: Verify battery parameter names in config_defaults**

```bash
grep -n "set_use_battery\|battery_target_state_of_charge\|battery_minimum_state_of_charge\|battery_maximum_state_of_charge\|battery_discharge_power_max\|battery_charge_power_max\|battery_discharge_efficiency\|battery_charge_efficiency" src/emhass/data/config_defaults.json
```
Expected: at least one match for each key.

- [ ] **Step 2.3: Verify runtime-param fields accepted by `treat_runtimeparams`**

```bash
grep -n "soc_init\|load_cost_forecast\|prod_price_forecast\|operating_hours_of_each_deferrable_load\|start_timesteps_of_each_deferrable_load\|end_timesteps_of_each_deferrable_load" src/emhass/utils.py
```
Expected: each name appears in the function body of `treat_runtimeparams` (around line 597-1100).

Note the line numbers — they will be cited in `<!-- source: utils.py:NNN -->` HTML comments inside the recipe files (per D9).

- [ ] **Step 2.4: Verify battery constraint structure in optimization.py**

```bash
grep -n "set_use_battery\|soc_init\|param_soc_init\|battery_minimum_state_of_charge\|battery_maximum_state_of_charge" src/emhass/optimization.py
```
Expected: matches around lines 145 (`cp.Parameter(..., name="soc_init")`), 842, 956, 1163, 2435, 2535, etc.

Note these line numbers for the battery-recipe Config and Snippet source citations.

- [ ] **Step 2.5: Halt-on-drift check**

If ANY of Steps 2.1-2.4 returns zero matches for a key in the canonical table at the top of this plan: STOP. The canonical names have drifted in upstream since 2026-05-11. Do NOT proceed to recipe writing. Append a `## Pivot Reason` section to this plan describing exactly which key(s) drifted, the new actual name (if discoverable), and report back via HANDOFF-RESULT `status: blocked`.

- [ ] **Step 2.6: No commit**

Discovery-only.

---

## Task 3: Create `docs/cookbook/_template.md`

**Files:**
- Create: `docs/cookbook/_template.md`

- [ ] **Step 3.1: Write the template**

Create `docs/cookbook/_template.md` with this exact content:

````markdown
---
orphan: true
---

<!--
Cookbook recipe template.

To contribute a recipe:
  1. Copy this file:  cp _template.md <category>_<pattern>.md   (e.g. ev_daily_commute.md)
  2. Fill the sections below.
  3. Add a link to your new recipe in `index.md` under the matching category.
  4. Open a PR.

Contributor rules (see DOC-cookbook design notes):
  - Config snippets MUST be source-verified against `src/emhass/utils.py` (treat_runtimeparams)
    or `src/emhass/optimization.py`. Include `<!-- source: <file>:<line> -->` HTML comments
    above each Config / Snippet code block.
  - Transport snippets (HA rest_command / Node-RED / EVCC / AppDaemon / Loxone) must mark
    which stack the recipe was tested against, or mark untested variants as such.
  - Keep total length under ~200 lines including code blocks.
-->

# Recipe Title

## Goal

One sentence — what does this recipe achieve?

## Prerequisites

- EMHASS version: e.g. ≥ X.Y
- Config flags / runtime env required (one per line)
- Transport stack tested against: e.g. Node-RED 3+, Home Assistant Core ≥ 2024.x, EVCC ≥ 0.x, etc.

## Config

<!-- source: src/emhass/path.py:LINE -->

```yaml
# EMHASS config keys, runnable as-is
```

## Snippet

<!-- source: src/emhass/path.py:LINE (if applicable) -->
<!-- transport: Node-RED 3.1 (tested) / HA rest_command (untested — community contribution welcome) -->

```js
// integration code, runnable
```

## Caveats

- Known limit one
- Known limit two
- Edge case when X

## Credits

- Pattern from Discussion #NNN (@handle)
- Prior art: `docs/study_cases/...md`
````

- [ ] **Step 3.2: Verify**

```bash
test -f docs/cookbook/_template.md && grep -c "^## " docs/cookbook/_template.md
```
Expected: file exists; section-header count = 5 (Goal, Prerequisites, Config, Snippet, Caveats, Credits — actually 6; accept ≥ 5).

- [ ] **Step 3.3: Commit**

```bash
git add docs/cookbook/_template.md
git commit -m "docs(cookbook): add recipe template (:orphan:)"
```

---

## Task 4: Create `docs/cookbook/nodered_mpc_orchestration.md`

**Files:**
- Create: `docs/cookbook/nodered_mpc_orchestration.md`

This recipe documents the generic Node-RED → EMHASS MPC pattern (no EVCC, no HA, no Loxone). Uses canonical parameter names verified in Task 2.

- [ ] **Step 4.1: Write the recipe**

Create `docs/cookbook/nodered_mpc_orchestration.md` with this content (replace the `LINE` placeholders in `<!-- source: ... -->` comments with the actual line numbers noted in Task 2.3):

````markdown
# MPC orchestration via Node-RED

## Goal

Drive EMHASS naive-MPC optimization from a Node-RED flow on any cadence, recomputing runtime parameters per call. Transport-agnostic on the EMHASS side; you pick any sensor source (Modbus, MQTT, HA bridge, manufacturer API) for the inputs.

## Prerequisites

- EMHASS reachable via HTTP on a known host:port (default `:5000`)
- Node-RED 3+ with the default `inject`, `function`, and `http request` nodes
- A static EMHASS config that already declares your deferrables / battery / thermal loads. This recipe only covers the *runtime params* (the values you change per MPC call). Static config lives in `config.yaml` / config-GUI.

## Config

Static EMHASS config skeleton (only the parts relevant to MPC orchestration are shown — your real config will have more). Names per `src/emhass/data/config_defaults.json`:

<!-- source: src/emhass/data/config_defaults.json -->

```yaml
optim_conf:
  set_use_battery: true                       # if you have a battery
  number_of_deferrable_loads: 2               # adjust to your setup
  nominal_power_of_deferrable_loads: [3000, 750]
  operating_hours_of_each_deferrable_load: [4, 0]      # overridden per MPC call
  start_timesteps_of_each_deferrable_load: [0, 0]      # overridden per MPC call
  end_timesteps_of_each_deferrable_load: [0, 0]        # overridden per MPC call
```

Runtime params accepted by `treat_runtimeparams` and overridden per MPC call:

<!-- source: src/emhass/utils.py:treat_runtimeparams (~line 597-1100) -->

| Field | Type | Purpose |
|---|---|---|
| `operating_hours_of_each_deferrable_load` | `list[int]` | hours each deferrable should run |
| `start_timesteps_of_each_deferrable_load` | `list[int]` | earliest allowed step per deferrable |
| `end_timesteps_of_each_deferrable_load` | `list[int]` | latest allowed step per deferrable |
| `load_cost_forecast` | `list[float]` | per-timestep tariff for load |
| `prod_price_forecast` | `list[float]` | per-timestep sell price for production |
| `soc_init` | `float` (0..1) | current battery state of charge as fraction |

## Snippet

<!-- transport: Node-RED 3.1 (tested against production setup); other languages welcome as separate recipes -->

A generic Node-RED flow shape — adapt to your sensor sources. Replace `<EMHASS_HOST>` with the EMHASS host:port. Do NOT copy verbatim, the field values are illustrative:

```text
[inject every 5 min] → [function: build runtime_params] → [http request: POST /action/naive-mpc-optim] → [debug]
```

**`function` node body** (JavaScript, what to put inside the Node-RED `function` node):

```javascript
// Read whatever sensor values your stack exposes via context / flow / msg.
// The example values below are placeholders — wire them to your actual sources.

const charger_kw = 11.0;
const timestep_min = 30;          // must match EMHASS optimization_time_step_minutes
const horizon_steps = 48;         // 48 × 30min = 24h

// Example: deferrable #2 is an EV, recompute its window each call
const ev_remaining_kwh = flow.get("ev_remaining_kwh") || 0;
const ev_hours = Math.ceil(ev_remaining_kwh / charger_kw);
const minutes_until_deadline = flow.get("minutes_until_deadline") || 480;
const end_step = Math.floor(minutes_until_deadline / timestep_min);

// Battery SOC from your battery monitor, normalized to fraction 0..1
const soc_percent = flow.get("battery_soc_percent") || 50;
const soc_init = soc_percent / 100;

// Per-timestep price arrays from your tariff source (length = horizon_steps)
const load_cost = flow.get("load_cost_per_step") || new Array(horizon_steps).fill(0.30);
const prod_price = flow.get("prod_price_per_step") || new Array(horizon_steps).fill(0.08);

msg.payload = {
  operating_hours_of_each_deferrable_load: [4, ev_hours],
  start_timesteps_of_each_deferrable_load: [0, 0],
  end_timesteps_of_each_deferrable_load: [horizon_steps, end_step],
  load_cost_forecast: load_cost,
  prod_price_forecast: prod_price,
  soc_init: soc_init
};
return msg;
```

**`http request` node configuration:**

- Method: `POST`
- URL: `http://<EMHASS_HOST>:5000/action/naive-mpc-optim`
- Headers: `Content-Type: application/json`
- Send: `as JSON`
- Timeout: at least 120 000 ms (long MPC runs)

## Caveats

- **Field-name versioning.** Runtime-param names are EMHASS-version-sensitive. If you upgrade EMHASS, regrep `src/emhass/utils.py` for the names you use; key renames are not always called out in release notes.
- **MPC timeout.** Default Node-RED `http request` timeout is short; raise to 120 s+ or the call will fail before EMHASS finishes the solve.
- **State between ticks.** Use `flow.set(...)` and `flow.get(...)` (not `context.set/get`) so the values survive Node-RED redeploys of unrelated tabs.
- **Error handling.** Wire a `catch` node downstream of the `http request` node; EMHASS returns HTTP 500 with a JSON error body on infeasible solves.
- **Length of price arrays.** `load_cost_forecast` and `prod_price_forecast` must have at least `horizon_steps` entries, otherwise EMHASS pads / truncates and you may not notice silent misalignment.
- **Battery SOC unit.** EMHASS expects `soc_init` as a fraction in [0, 1]. The HA SOC sensor is typically percent; divide by 100. See [Battery-aware runtime params](battery_aware_runtime_params.md) for the full story.

## Credits

- Prior art: long-form MPC walkthrough at `docs/study_cases/mpc.md`.
- Pattern derived from author's production Node-RED setup (no private flow JSON included; only generic shape).
- Field names verified against `src/emhass/utils.py:treat_runtimeparams` and `src/emhass/data/config_defaults.json` on 2026-05-11.
````

- [ ] **Step 4.2: Update source-citation line numbers**

Re-grep the line numbers noted in Task 2.3 and patch the `<!-- source: ... -->` comments in the recipe to cite specific lines (e.g. `<!-- source: src/emhass/utils.py:968 -->`).

Run:
```bash
grep -n "operating_hours_of_each_deferrable_load" src/emhass/utils.py | head -3
```

Pick the line that is inside the `treat_runtimeparams` function body (closest to line 600-1100 range) and update the recipe's `<!-- source: ... -->` comment accordingly. Repeat for `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load`, `load_cost_forecast`, `prod_price_forecast`, `soc_init` if you want per-key citations (or keep the single function-range citation).

- [ ] **Step 4.3: Privacy lint pass**

```bash
grep -iE "loxone|192\.168|10\.0|172\.16|\.lan|\.local" docs/cookbook/nodered_mpc_orchestration.md
```
Expected: zero matches. If any match: redact and re-grep.

- [ ] **Step 4.4: Length check**

```bash
wc -l docs/cookbook/nodered_mpc_orchestration.md
```
Expected: ≤ 200 lines.

- [ ] **Step 4.5: Commit**

```bash
git add docs/cookbook/nodered_mpc_orchestration.md
git commit -m "docs(cookbook): add Node-RED MPC orchestration recipe"
```

---

## Task 5: Create `docs/cookbook/battery_aware_runtime_params.md`

**Files:**
- Create: `docs/cookbook/battery_aware_runtime_params.md`

This recipe focuses on the live-SOC feedback pattern. Cross-references the upcoming `docs/plan_output_schema.md` (from PR #835 — once merged) for SOC scaling.

- [ ] **Step 5.1: Write the recipe**

Create `docs/cookbook/battery_aware_runtime_params.md` with this content:

````markdown
# Battery-aware runtime params

## Goal

Feed live battery state of charge (SOC) back into EMHASS naive-MPC on every call so the optimizer plans against the real current state, not a stale assumption. Avoid the most common consumer bug: SOC unit mismatch (fraction vs percent).

## Prerequisites

- Battery is enabled in your static EMHASS config:

  ```yaml
  optim_conf:
    set_use_battery: true
  plant_conf:
    battery_target_state_of_charge: 0.6
    battery_minimum_state_of_charge: 0.3
    battery_maximum_state_of_charge: 0.9
    battery_discharge_power_max: 5000
    battery_charge_power_max: 5000
    battery_discharge_efficiency: 0.95
    battery_charge_efficiency: 0.95
  ```

  (Names per `src/emhass/data/config_defaults.json`.)
- A battery SOC sensor reachable from your orchestrator (Node-RED, AppDaemon, etc.). Common sources: inverter Modbus register, manufacturer cloud API, HA `sensor.battery_state_of_charge`. Any source works as long as you can read a number.
- An MPC orchestrator that already POSTs to `/action/naive-mpc-optim`. If you don't have one yet, see [MPC orchestration via Node-RED](nodered_mpc_orchestration.md).

## Config

<!-- source: src/emhass/data/config_defaults.json:110-117 -->

The static battery block above is the input contract. The single runtime param this recipe drives is `soc_init`:

<!-- source: src/emhass/utils.py:933 (treat_runtimeparams reads soc_init) -->

| Field | Type | Range | Notes |
|---|---|---|---|
| `soc_init` | `float` | `[battery_minimum_state_of_charge, battery_maximum_state_of_charge]` | Fraction 0..1, NOT percent. EMHASS logs a warning and refuses values outside [SOCmin, SOCmax]. |

EMHASS will reject `soc_init` outside the configured min / max bounds:

<!-- source: src/emhass/utils.py:937-944 (soc_init bound-check) -->

- If `soc_init < battery_minimum_state_of_charge`: EMHASS warns "Passed soc_init=... is lower than soc_min=..., keeping real initial SOC for optimization recovery" and falls back.
- If `soc_init > battery_maximum_state_of_charge`: equivalent warning, same fallback.

## Snippet

<!-- transport: Node-RED 3.1 (tested) — patterns translate directly to AppDaemon, Python, etc. -->

Append to the runtime_params your MPC orchestrator already sends. Generic Node-RED `function` node fragment:

```javascript
// Read whatever sensor exposes battery SOC. Examples:
//   const soc_percent = flow.get("battery_soc_percent");      // your-stack-specific
//   const soc_percent = msg.payload;                          // if previous node was a sensor read
//   const soc_percent = global.get("home_battery").soc;       // global context store

const soc_percent = flow.get("battery_soc_percent") || 50;

// EMHASS expects fraction. Divide percent by 100.
const soc_init = soc_percent / 100;

// Validate against configured min/max BEFORE sending — saves a round-trip warning log.
const SOC_MIN = 0.3;   // your battery_minimum_state_of_charge
const SOC_MAX = 0.9;   // your battery_maximum_state_of_charge
const soc_init_clamped = Math.max(SOC_MIN, Math.min(SOC_MAX, soc_init));

if (soc_init_clamped !== soc_init) {
  node.warn(`SOC ${soc_init} clamped to [${SOC_MIN}, ${SOC_MAX}]`);
}

msg.payload = msg.payload || {};
msg.payload.soc_init = soc_init_clamped;
return msg;
```

Wire this `function` node in series before the `http request` node from the [Node-RED MPC orchestration recipe](nodered_mpc_orchestration.md).

## Caveats

- **#1 bug: percent vs fraction.** EMHASS works in fraction (0..1). Most sensor sources expose percent (0..100). Always check the unit. Symptoms of getting it wrong: optimizer plans aggressive discharge (thinks battery is "full" at 80 because it sees 0.8 as 80% margin headroom), or plans aggressive charge (thinks battery is empty). See the [Plan-output schema](plan_output_schema.md) for the symmetric output-side scaling trap on `SOC_opt`.
- **Stale sensor.** If your battery sensor publishes only on change and your MPC ticks every 5 min, a long idle period can serve stale SOC. Wire a `delay` node with `last value` semantics, or read a "last_updated" timestamp and reject readings older than 2× MPC period.
- **Bound rejection is silent in the optimizer.** EMHASS *only* logs a warning when `soc_init` is out of range; the solve continues with the fallback. If you depend on the value being honored, validate before sending (the snippet above does this).
- **Hardware BMS still owns safety.** EMHASS does not enforce battery safety limits — it computes a *plan*. Your battery's BMS / inverter must still enforce its own thermal, voltage, and current limits. EMHASS plans things the hardware can refuse.
- **SOC at horizon end.** EMHASS plans to land at `battery_target_state_of_charge` by horizon end by default. If you want a different terminal SOC for a specific call, pass `soc_final` in runtime params. (Out of scope for this recipe — see EMHASS naive-MPC docs for the full runtime-param list.)

## Credits

- SOC fraction-vs-percent gotcha discovered while building [PR #835 plan-output schema doc](https://github.com/davidusb-geek/emhass/pull/835). See `docs/plan_output_schema.md` (once #835 merges) for the symmetric output-side story.
- Field names verified against `src/emhass/utils.py:treat_runtimeparams` and `src/emhass/optimization.py` battery constraints on 2026-05-11.
- Pattern derived from author's production setup (battery in EMHASS-Optim; generic only, no private config).
````

- [ ] **Step 5.2: Update source-citation line numbers**

Re-grep the actual line numbers (some are already inlined like `:933`, `:937-944`). Cross-check:
```bash
grep -n "soc_init" src/emhass/utils.py | head -10
grep -n "battery_minimum_state_of_charge\|battery_maximum_state_of_charge" src/emhass/utils.py | head -5
grep -n '"battery_discharge_power_max"\|"battery_charge_power_max"\|"battery_discharge_efficiency"\|"battery_charge_efficiency"\|"battery_minimum_state_of_charge"\|"battery_maximum_state_of_charge"\|"battery_target_state_of_charge"' src/emhass/data/config_defaults.json
```
If line numbers differ from what's embedded (`:933`, `:937-944`, `:110-117`), update the `<!-- source: ... -->` comments to the actual numbers.

- [ ] **Step 5.3: Privacy lint pass**

```bash
grep -iE "loxone|192\.168|10\.0|172\.16|\.lan|\.local" docs/cookbook/battery_aware_runtime_params.md
```
Expected: zero matches.

- [ ] **Step 5.4: Length check**

```bash
wc -l docs/cookbook/battery_aware_runtime_params.md
```
Expected: ≤ 200 lines.

- [ ] **Step 5.5: Commit**

```bash
git add docs/cookbook/battery_aware_runtime_params.md
git commit -m "docs(cookbook): add battery-aware runtime params recipe"
```

---

## Task 6: Create `docs/cookbook/index.md`

**Files:**
- Create: `docs/cookbook/index.md`

- [ ] **Step 6.1: Write the index**

Create `docs/cookbook/index.md` with exactly this content:

````markdown
# Cookbook

Short, standalone, copy-pasteable recipes for common EMHASS patterns. Each recipe follows a fixed template: Goal / Prerequisites / Config / Snippet / Caveats / Credits.

> If you need a longer narrative walkthrough, see [Study Cases](../study_cases/index.md). The Cookbook is the [Diátaxis](https://diataxis.fr/) **how-to-guide** quadrant — short, task-oriented, scannable.

## How to contribute

1. Copy `_template.md` to `<category>_<pattern>.md` (e.g. `ev_calendar_driven.md`).
2. Fill the 6 sections.
3. Link your file under the matching category below.
4. Open a PR. Contributor rules are inside the template.

## Recipes by category

### EV charging

No recipes yet. **EVCC integration architecture is under active discussion** at [evcc-io/evcc#29815](https://github.com/evcc-io/evcc/discussions/29815) — EV-EVCC-coupled recipes will land after that resolves.

Seed material for HA-flavored EV recipes (community contributions welcome): [Discussion #824](https://github.com/davidusb-geek/emhass/discussions/824) thread (daily-commute, surplus-only, multi-day, calendar-driven, negative-price-aware, modulating-power patterns).

### Domestic hot water (DHW)

No recipes yet. See `docs/study_cases/dhw_walkthrough.md` for the long-form walkthrough. Contributions welcome.

### Heat pump

No recipes yet. See `docs/study_cases/heat_pump_walkthrough.md` for the long-form walkthrough. Contributions welcome.

### Battery

- [Battery-aware runtime params](battery_aware_runtime_params.md) — feed live SOC into MPC; avoids the percent/fraction gotcha.

Additional battery recipes welcome (charging-from-grid strategies, calendar-aware reservation, etc.) — see [Discussion #823](https://github.com/davidusb-geek/emhass/discussions/823) for good-practices crowdsourcing.

### Forecast

No recipes yet. Topics that would fit: ML vs naive load forecaster selection, custom forecast injection via runtime params, dealing with forecast outages. Contributions welcome.

### Tariff

No recipes yet. Topics that would fit: dynamic-price (EPEX, Tibber, etc.) injection, multi-tier tariffs, sell-vs-self-consume thresholds. Contributions welcome.

### Transport / integration

- [MPC orchestration via Node-RED](nodered_mpc_orchestration.md) — generic Node-RED → EMHASS pattern, transport-agnostic on inputs.

Additional transport recipes welcome: Home Assistant `rest_command` (HA users — see [Discussion #824](https://github.com/davidusb-geek/emhass/discussions/824) for community patterns), AppDaemon, EVCC API integration (pending #29815), Loxone-direct, etc.
````

- [ ] **Step 6.2: Verify**

```bash
test -f docs/cookbook/index.md
grep -c "^### " docs/cookbook/index.md
```
Expected: file exists, 7 category headers.

- [ ] **Step 6.3: Commit**

```bash
git add docs/cookbook/index.md
git commit -m "docs(cookbook): add index page with category structure"
```

---

## Task 7: Wire `cookbook/index` into `docs/index.md` toctree

**Files:**
- Modify: `docs/index.md`

- [ ] **Step 7.1: Locate the toctree directive containing `study_cases/index`**

```bash
grep -n "study_cases/index" docs/index.md
```
Expected: at least one match. Note the line number — this is the toctree we want to extend.

- [ ] **Step 7.2: Read the toctree context**

```bash
grep -B 5 -A 5 "study_cases/index" docs/index.md
```
Identify whether `study_cases/index` is inside a `{toctree}` directive and what its peers are.

- [ ] **Step 7.3: Insert `cookbook/index` immediately after `study_cases/index`**

Edit `docs/index.md`. Find the line:
```
study_cases/index
```

Change to:
```
study_cases/index
cookbook/index
```

(Indentation must match the surrounding lines in the toctree — copy the existing indentation exactly.)

- [ ] **Step 7.4: Verify**

```bash
grep -n "cookbook/index" docs/index.md
```
Expected: 1 match, on the line immediately after `study_cases/index`.

- [ ] **Step 7.5: Commit**

```bash
git add docs/index.md
git commit -m "docs(nav): add cookbook to top-level toctree"
```

---

## Task 8: Build docs locally to catch render errors

- [ ] **Step 8.1: Sphinx build**

Run (Windows pwsh):
```bash
cd docs
./make.bat html
cd ..
```

Or:
```bash
sphinx-build -b html docs docs/_build/html
```

Expected: build succeeds. Warnings naming `cookbook/index.md`, `cookbook/_template.md`, `cookbook/nodered_mpc_orchestration.md`, or `cookbook/battery_aware_runtime_params.md` are NOT acceptable. Warnings about unrelated docs are OK.

The `_template.md` has `orphan: true` in frontmatter — it should NOT produce a "document isn't in any toctree" warning. If it does, double-check the frontmatter syntax (MyST uses `---\norphan: true\n---` block).

If `make.bat` / `sphinx-build` is not installed locally: skip Step 8.1 and rely on the GitHub PR preview. Note the skip in the PR description.

- [ ] **Step 8.2: Open rendered HTML (optional)**

Open `docs/_build/html/cookbook/index.html`. Verify:
- All 7 category headers render.
- Links to `nodered_mpc_orchestration.html` and `battery_aware_runtime_params.html` resolve.
- The link to `study_cases/index` resolves.

Open `docs/_build/html/cookbook/nodered_mpc_orchestration.html` and `docs/_build/html/cookbook/battery_aware_runtime_params.html`. Verify:
- All 6 section headers (Goal, Prerequisites, Config, Snippet, Caveats, Credits) render.
- Code blocks highlight.
- Cross-reference link in the battery recipe (to `nodered_mpc_orchestration.md`) resolves.

- [ ] **Step 8.3: No commit**

Build artifacts under `docs/_build/` are gitignored.

---

## Task 9: Aggregate privacy lint across all new files

**Files:** read-only

This is a final paranoia pass. Spec D4c requires zero leaks of private-repo content into public docs.

- [ ] **Step 9.1: Run the broad lint**

```bash
grep -riE "loxone|loxonesmarthome|192\.168|10\.0\.|172\.(1[6-9]|2[0-9]|3[01])\.|\.lan\b|\.local\b|U:/|U:\\\\|/nodered/" docs/cookbook/
```

Expected: zero matches. If any match: investigate, redact, re-grep, then proceed.

- [ ] **Step 9.2: Sanity-check for obvious private hostnames / device names**

If you know specific private identifiers (e.g. specific inverter brand serial fragments, custom HA sensor IDs from the author's stack), grep for those too. Default: skip; the broad lint in Step 9.1 catches the obvious classes.

- [ ] **Step 9.3: No commit**

If Step 9.1 returned matches: do not proceed to Task 10. Fix and recommit the affected recipe.

---

## Task 10: Push branch + open PR

- [ ] **Step 10.1: Push**

```bash
git push -u origin docs/doc-cookbook
```

- [ ] **Step 10.2: Open PR**

Use this exact title:
```
docs(cookbook): scaffold cookbook section + Node-RED MPC + battery-aware seed recipes
```

Body: use the verbatim PR body block from the `## Handoff-Prompt` section at the bottom of this plan.

Windows pwsh:
```powershell
$body = @'
<paste body from Handoff-Prompt section verbatim>
'@
$bodyFile = New-TemporaryFile
Set-Content -Path $bodyFile -Value $body -Encoding UTF8
gh pr create `
  --repo davidusb-geek/emhass `
  --base master `
  --head OptimalNothing90:docs/doc-cookbook `
  --title "docs(cookbook): scaffold cookbook section + Node-RED MPC + battery-aware seed recipes" `
  --body-file $bodyFile
Remove-Item $bodyFile
```

Expected: PR URL printed.

- [ ] **Step 10.3: Capture URL**

```bash
gh pr view --json url -q .url
```

---

## Task 11: Report HANDOFF-RESULT

- [ ] **Step 11.1: Compose result block**

Paste into orchestrator session:

```
HANDOFF-RESULT DOC-cookbook
status: pr-open
pr-url: <URL from Task 10.3>
branch: docs/doc-cookbook
tests: source-trace verified (all canonical names found in config_defaults.json + utils.py + optimization.py); sphinx build clean; privacy lint zero matches
notes: 2 seed recipes (Node-RED MPC orchestration, battery-aware runtime params), index has 7 categories with EV stub gated on evcc-io#29815; cross-link from study_cases/ev.md deferred to first EV recipe per spec D6
```

---

## Self-review checklist

Run before declaring done:

- [ ] All canonical parameter names match `config_defaults.json` (no `SOCtarget`, `Pd_max`, `def_total_hours` remnants)? Verify with: `grep -E "SOCtarget|Pd_max|Pc_max|eta_disch|eta_ch|def_total_hours" docs/cookbook/` → must return zero.
- [ ] Each `<!-- source: ... -->` comment cites a real `:line` number (verified in Task 4.2 / 5.2)?
- [ ] Both recipes ≤ 200 lines?
- [ ] Privacy lint passes on both recipes AND the index (Task 9)?
- [ ] `_template.md` has `orphan: true` and does NOT appear in any toctree?
- [ ] `cookbook/index` appears in `docs/index.md` toctree?
- [ ] `study_cases/ev.md` is **unmodified** in this PR?
- [ ] PR title is conventional commit `docs(cookbook): ...`?
- [ ] PR body acknowledges D2 ambiguity, explains seed-choice rationale, invites community for EV-EVCC (pending #29815) and HA?
- [ ] Branch name is exactly `docs/doc-cookbook`?

If any answer flips to "No": STOP and append a `## Pivot Reason` section to this plan, then hand back via HANDOFF-RESULT `status: blocked`.

## Handoff-Prompt

**Copy-paste into a NEW Claude Code session opened in `C:/Users/MauricioSchäpers/claude-code/emhass/` (the fork):**

````
You are a fork-session for emhass upstream PR work. The main planning session lives in
`C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`. You operate ONLY here in
the `emhass` fork repo.

## Item context
- Board ID: DOC-cookbook
- Discussion: https://github.com/davidusb-geek/emhass/discussions/824 (David approved 2026-04-28)
- Sibling Discussion: https://github.com/evcc-io/evcc/discussions/29815 (EVCC integration architecture, gates EV-EVCC recipes)
- Goal-fit: (empty — non-goal hygiene, but maintainer-blessed)
- Spec: `docs/superpowers/specs/2026-05-10-doc-cookbook-design.md`
- Plan: `docs/superpowers/plans/2026-05-10-doc-cookbook.md`

The spec and plan are in the sibling repo. Read them via:
  cat ../emhass-contributions/docs/superpowers/specs/2026-05-10-doc-cookbook-design.md
  cat ../emhass-contributions/docs/superpowers/plans/2026-05-10-doc-cookbook.md

## Pre-flight (mandatory, in order)
1. `gh auth status` — must show `OptimalNothing90` active. Switch with
   `gh auth switch --user OptimalNothing90` if not.
2. `git fetch upstream && git checkout upstream/master`
3. `git checkout -b docs/doc-cookbook` (exact name, do not invent)
4. Verify clean tree before edits: `git status` should show empty.

## Implementation
Use `superpowers:executing-plans`. Plan path:
`../emhass-contributions/docs/superpowers/plans/2026-05-10-doc-cookbook.md`.
Follow the plan step-by-step. Do NOT improvise scope.

CRITICAL — Task 2 source-trace verification MUST run before any recipe is written.
The plan's "Canonical EMHASS parameter names" table at the top was verified on
2026-05-11; if any name has drifted in upstream since then, STOP and file a Pivot
Reason per Task 2.5.

CRITICAL — Privacy discipline (spec D4c). Recipes are PUBLIC. No `loxone`, no private
IPs, no `loxonesmarthome` repo strings, no internal hostnames, no actual flow JSON from
the production setup. Generic patterns only. Task 9 runs an aggregate privacy lint
that MUST pass with zero matches before opening the PR.

## PR creation
After all plan tasks complete and verification steps pass:

  git push -u origin docs/doc-cookbook

Then create the PR with this exact title and body:

  Title: docs(cookbook): scaffold cookbook section + Node-RED MPC + battery-aware seed recipes

  Body (write to a temp file then pass via --body-file):

## Summary
Scaffolds a new `docs/cookbook/` section in the EMHASS docs tree following the [Diátaxis](https://diataxis.fr/) how-to-guide quadrant: short, standalone, task-oriented recipes, distinct from `docs/study_cases/` which stays for long-form narrative walkthroughs.

Adds two seed recipes drawn from patterns the author runs in production:

1. **MPC orchestration via Node-RED** (`cookbook/nodered_mpc_orchestration.md`) — generic transport-agnostic pattern for driving `/action/naive-mpc-optim` on a cadence with per-call runtime params.
2. **Battery-aware runtime params** (`cookbook/battery_aware_runtime_params.md`) — feeding live `soc_init` back into MPC, with explicit treatment of the fraction-vs-percent gotcha that PR #835 documented for `SOC_opt` on the output side.

Both recipes Config + Snippet sections are source-verified against `src/emhass/utils.py` (treat_runtimeparams), `src/emhass/optimization.py` (battery constraints), and `src/emhass/data/config_defaults.json`. Inline source-citation HTML comments above code blocks (invisible in render, visible to reviewers).

Approved in Discussion #824 on 2026-04-28.

## Files changed
- `docs/cookbook/index.md` — landing page with 7 category sections (EV / DHW / Heat pump / Battery / Forecast / Tariff / Transport-integration); Transport-integration + Battery seeded with 1 recipe each, rest are "contributions welcome" stubs
- `docs/cookbook/_template.md` — copy-paste template for contributors, `:orphan:` (not in toctree by design)
- `docs/cookbook/nodered_mpc_orchestration.md`
- `docs/cookbook/battery_aware_runtime_params.md`
- `docs/index.md` — toctree gains `cookbook/index` as peer of `study_cases/index`

NOT touched:
- `docs/study_cases/ev.md` — cross-link from there to cookbook is deferred to the first EV-recipe PR.
- No EVCC-flavored recipes — pending evcc-io#29815. Index EV section carries that cross-link.

## On the cookbook-vs-walkthroughs framing

David, your Discussion #824 approval said "complete walkthroughs on a cookbook section". I read "complete" as **standalone-readable** (each recipe self-contained) rather than **long-form**, and went scikit-learn / pandas Cookbook style (≤ 200 lines, fixed template). That convention is what most Python projects mean by "Cookbook" today. If you intended walkthroughs (long-form), flag it in review — the template extends, the recipes can grow. Easier to expand than to shrink.

## On the seed-recipe choice

- The two seeds are intentionally EVCC-neutral and HA-neutral. The author runs both patterns in production today, can source-verify both, and neither preempts the EVCC integration discussion at evcc-io#29815.
- HA `rest_command` recipes invited from community contributors who run HA (author does not).
- Author can follow up with additional Node-RED patterns and generic Loxone-integration patterns (private flow JSON never copied).

## Source verification

All Config + Snippet code blocks carry `<!-- source: <file>:<line> -->` comments citing upstream code. Canonical names per `config_defaults.json` + `utils.py:treat_runtimeparams` + `optimization.py` battery constraints (verified 2026-05-11).

## Test plan
- grep for folklore-name remnants in `docs/cookbook/` returns zero matches
- Sphinx build succeeds with no warnings naming any new file
- Privacy lint returns zero matches
- Manual render check on the four new HTML files

## Notes
- No automated test added (docs PR).
- Independent of PR #830 and PR #835. The battery recipe cross-references `docs/plan_output_schema.md` (added by #835 once merged).

## Return contract — required output back to main session
Send the user a single message in this format so they can paste it into the
main planning session:

HANDOFF-RESULT DOC-cookbook
status: pr-open | blocked | failed
pr-url: <url-or-none>
branch: docs/doc-cookbook
tests: pass | fail | skipped
notes: <one-line summary OR pivot reason if blocked>

## Pivot trigger (if plan is wrong)
If during implementation you discover the plan does not match upstream code reality
(file moved, function renamed, canonical parameter name drifted from the table in the
plan, assumption broken):
1. Do NOT improvise a new plan.
2. Do NOT push partial work.
3. Stop, write a `## Pivot Reason` section appended to
   `../emhass-contributions/docs/superpowers/plans/2026-05-10-doc-cookbook.md` with
   concrete divergence facts (file:line citations).
4. Set Return-status to `blocked`. Main session re-plans.

## Out of scope (this session)
- Spec edits — those happen in main session
- Board mutations — those happen in main session via `emhass-board-merge-bookkeeping`
- Account switching back — main session handles after merge
- Cross-link from `study_cases/ev.md` to cookbook — deferred per plan / spec D6
- EVCC-flavored recipes — deferred pending evcc-io#29815
````

After Fork-Session reports HANDOFF-RESULT, return to the main planning session and paste
the result block. Main session will:
- On `pr-open`: update Board-Card to `Status: Review`, add PR sibling card
- On `blocked`: read appended Pivot Reason, re-plan
- On `failed`: triage, decide
