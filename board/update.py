#!/usr/bin/env python3
"""
Apply post-migration corrections to the EMHASS AI agents dev board:
- Update 7 card bodies (AC-1, AC-2, AC-3, AC-4, AM-1, AM-3, AM-4) with verified source-state
- Create 2 new cards (AC-2a unit-field, AC-2-fix audit mismatches)
- Sync items.json source-of-truth

Idempotent? No — runs once. Existing items don't get duplicates because we update by ID.
New items will be added every run, so DON'T re-run after success without commenting out the create section.
"""

import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "2026-04-28-emhass-board-migration-items.json"
PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# Existing draft IDs (fetched 2026-04-28)
DRAFT_IDS = {
    "AC-1": "DI_lAHOAfZrVs4BV1jUzgKbxBs",
    "AC-2": "DI_lAHOAfZrVs4BV1jUzgKbxB8",
    "AC-3": "DI_lAHOAfZrVs4BV1jUzgKbxCE",
    "AC-4": "DI_lAHOAfZrVs4BV1jUzgKbxCU",
    "AM-1": "DI_lAHOAfZrVs4BV1jUzgKbxCY",
    "AM-3": "DI_lAHOAfZrVs4BV1jUzgKbxEM",
    "AM-4": "DI_lAHOAfZrVs4BV1jUzgKbxEY",
}


def gh(args, stdin=None):
    r = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, encoding="utf-8", input=stdin
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {r.stderr}")
    return r.stdout


def update_draft(draft_id: str, body: str) -> None:
    q = f"""mutation($body: String!) {{
      updateProjectV2DraftIssue(input: {{
        draftIssueId: "{draft_id}"
        body: $body
      }}) {{ draftIssue {{ id title }} }}
    }}"""
    out = gh(["api", "graphql", "-f", f"query={q}", "-f", f"body={body}"])
    print(
        f"  updated {json.loads(out)['data']['updateProjectV2DraftIssue']['draftIssue']['title']}"
    )


def add_draft_with_fields(
    title: str, body: str, fields: dict, option_ids: dict, field_ids: dict
) -> str:
    body_esc = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    title_esc = title.replace("\\", "\\\\").replace('"', '\\"')
    q = f"""mutation {{
      addProjectV2DraftIssue(input: {{
        projectId: "{PROJECT_ID}"
        title: "{title_esc}"
        body: "{body_esc}"
      }}) {{ projectItem {{ id }} }}
    }}"""
    out = gh(["api", "graphql", "-f", f"query={q}"])
    item_id = json.loads(out)["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]
    for fname, fval in fields.items():
        fq = f"""mutation {{
          updateProjectV2ItemFieldValue(input: {{
            projectId: "{PROJECT_ID}"
            itemId: "{item_id}"
            fieldId: "{field_ids[fname]}"
            value: {{ singleSelectOptionId: "{option_ids[fname][fval]}" }}
          }}) {{ projectV2Item {{ id }} }}
        }}"""
        gh(["api", "graphql", "-f", f"query={fq}"])
    print(f"  created [{item_id}] {title}")
    return item_id


# Load JSON for field_ids and option_ids
with DATA_FILE.open(encoding="utf-8") as f:
    data = json.load(f)
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

# === BODY UPDATES ===
NEW_BODIES = {
    "AC-1": """Document published columns of the optimization output as `docs/plan_output_schema.md`. Plus a `emhass_schema_version` constant for downstream-consumer version-pinning.

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
- 5 publish helpers in src/emhass/command_line.py:
  - _publish_standard_forecasts (line 2152) — P_Load, P_PV, P_PV_curtailment, P_hybrid_inverter
  - _publish_deferrable_loads (line 2215) — P_deferrable{k}, optim_status
  - _publish_thermal_loads (line 2260) — predicted_temp_heater{k}, heating_demand_heater{k}
  - _publish_battery_data (line 2305) — P_batt, SOC_opt
  - _publish_grid_and_costs (line 2342) — P_grid, cost_fun_*, unit_load_cost, unit_prod_price
- Aggregator at line 2464-2468 in publish helper.
- No docs/plan_output_schema.md exists today.

Deliverable (single PR):
- New file docs/plan_output_schema.md listing each column with: name, source helper, units, sign convention, conditional presence (e.g. SOC_opt only when set_use_battery=true), HA-scaling note for SOC_opt (0..1 in CSV vs ×100 in HA).
- Add emhass_schema_version constant in command_line.py (e.g. "1.0") published alongside results.
- Cross-link from docs/study_cases/ where relevant.

Sign-convention verification needed before publishing schema (P_grid sign, P_batt charge vs discharge convention) — flag in PR for maintainer confirmation.""",
    "AC-2": """**Umbrella card.** Track of structured-schema work on src/emhass/static/data/param_definitions.json (Maintainer-preferred surface, per #808). Split into deliverables tracked as separate cards:

- **AC-2a** (separate card): Add structured `unit` field to all 87 existing entries. Issue-first; specific scope.
- **AC-2b** (this card, future scope): Add ~30+ runtime/MPC params currently undocumented (prediction_horizon, soc_init/final, def_total_hours/timestep, prod_price_forecast, load_cost_forecast, pv_power_forecast, load_power_forecast, min_temperatures, max_temperatures, def_start_timestep, def_end_timestep, plus runtime overrides like battery_nominal_energy_capacity). Today only documented in passing_data.md prose.
- **AC-2-fix** (separate card): Audit-found mismatches between param_definitions.json defaults/types and config_defaults.json + utils.treat_runtimeparams.

Sequencing: AC-2a first (additive, no risk) → AC-2-fix in parallel (independent fix PR) → AC-2b after AC-2a merge → unblocks AM-1 (openapi.json) and AM-2 (auto-gen config.md).

Current state (verified 2026-04-28 against upstream/master):
- 87 entries / 6 categories: Local (18), System (23), Tariff (6), Solar System PV (11), Deferrable Loads (10), Battery (19)
- Schema: friendly_name + Description + input + default_value (+ optional select_options, requires, input_attributes)
- Missing per-entry: structured unit, formal type, range, required-flag
- Missing entirely: runtime/MPC params block""",
    "AC-3": """Read-only JSON endpoint exposing the last optimization run's metadata: stage_times dict (PR #806 plumbing), solver status, infeasibility flag, schema_version (AC-1 dependency).

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
- src/emhass/command_line.py line 749/847: `_prepare_dayahead_optim` and `_prepare_naive_mpc_optim` accept `stage_times: dict | None = None` parameter.
- Stage timer wraps pv_forecast (line 758) and load_forecast (line 763).
- Stage data is collected in input_data_dict — exact attachment point needs code-trace before PR.
- src/emhass/web_server.py has 9 routes today: /, /index, /configuration, /template, /get-config, /get-config/defaults, /get-json, /set-config, /action/<action_name>.
- No /api/last-run, no /metrics endpoint.

Threat model per #808 Maintainer comment: code-injection (NOT auth-bypass / data-leakage). Endpoint reads in-memory state only — no DB writes, no FS writes, no shell-out, no dynamic-code execution surface.

Deliverable: ~30-50 LOC in web_server.py, JSON response schema documented, security-pitch in PR description.""",
    "AC-4": """Liveness/readiness endpoint for container watchdog. Exposes boot status, last-successful-run timestamp, EMHASS version + solver lib versions.

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
- 9 routes in web_server.py (see AC-3 list); no /healthz.
- Banner from PR #806 already prints version info to logs at start of run — same data could populate /healthz response.

Deliverable: ~15 LOC in web_server.py. Response schema:
```json
{
  "status": "ok|degraded|down",
  "boot_ts": "<iso8601>",
  "last_run_ts": "<iso8601>|null",
  "last_run_status": "ok|infeasible|error|null",
  "versions": {"emhass": "...", "python": "...", "cvxpy": "...", "solver": "..."}
}
```
Auth-flag-aware: same gating as existing /get-config. Read-only. No sensitive data.""",
    "AM-1": """Commit src/emhass/static/openapi.json + scripts/generate_openapi.py to the repo. Tool consumers (Node-RED validators, EVCC adapters, HA cards, IDE tooling) read the API contract without booting EMHASS.

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
- No openapi.json, no openapi.yaml in the repo.
- web_server.py has 9 routes (see AC-3 list). All /action/* endpoints accept similar runtime-payload bodies with no published schema.

Sequencing: depends on AC-2a (unit field), AC-2b (runtime params block), AC-1 (plan output schema). Once schema is structured, openapi.json generation is mechanical — Pydantic models from param_definitions.json generate request schemas; AC-1 doc gives response schema.

Deliverable:
- scripts/generate_openapi.py: reads param_definitions.json + plan_output_schema.md → emits openapi.json
- openapi.json committed at repo root or src/emhass/static/openapi.json
- CI workflow check: re-run script on PR, fail if generated diff != committed file
- Folge zu #808 Layer 2.""",
    "AM-3": """Strategy pattern for forecast providers. Reduce merge conflicts between parallel provider PRs (#787 Octopus, #745 Solcast-cap, #803 InfluxDB-Math).

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
Three independent if/elif cascades in src/emhass/forecast.py:
- get_weather_forecast (line 574): scrapper / solcast / solar.forecast / csv / list
- get_load_forecast (line 1517): typical / naive / mlforecaster / csv / list
- get_load_cost_forecast (line 1605): hp_hc_periods / ...

Pilot scope: refactor ONE cascade (recommend get_load_cost_forecast — smallest, lowest risk). Pattern: abstract base class + concrete subclasses per method. New providers register via subclass + class attribute (not if/elif edit). Existing call site stays binary-compatible.

Issue-first per #808 corridor — RFC issue with proposed ABC + one example provider conversion. Wait for maintainer architecture green-light before code PR.""",
    "AM-4": """Extract HA-specific glue code from src/emhass/retrieve_hass.py + command_line.py into src/emhass/adapters/ subfolder. Makes the #789 Maintainer line ("agnostic glue layer via NR/MQTT/HA") structurally explicit.

Current state (verified 2026-04-28 against upstream/master @ 6537c47):
- No adapters/ folder in src/emhass/.
- Glue code currently in retrieve_hass.py (HA-specific REST + websocket) and command_line.py (mixed orchestration + HA helpers).

Pilot scope: create adapters/{ha,nodered,mqtt}.py skeletons. Move HA-specific code from retrieve_hass.py → adapters/ha.py. Keep retrieve_hass.py as thin facade (backward-compat). Add adapters/__init__.py with adapter registry.

Depends on AM-3 pattern being established — same Strategy/Adapter style. Issue-first.

Sequencing: AM-3 first (provider abstraction proves pattern in small surface) → AM-4 (apply same pattern to glue layer).""",
}

# === NEW ITEMS ===
NEW_ITEMS = [
    {
        "id": "AC-2a",
        "title": "AC-2a: Add `unit` field to param_definitions.json",
        "body": """Add structured `unit` field to all ~80 existing entries in src/emhass/static/data/param_definitions.json. Parse-friendly metadata enables openapi-spec generation (AM-1), Pydantic models, and AI-readable schemas.

Source: detailed prompt at docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json (item AC-2a).

Process (issue-first):
1. Open issue on davidusb-geek/emhass: "Add structured `unit` field to param_definitions.json for AI/openapi readability". Reference #808 Layer-2 invitation. Propose enum, ask blessing before PR.
2. Wait for maintainer response. NO code yet.
3. After approval: branch `feat/param-definitions-unit-field` from upstream/master.
4. Add `"unit": "<value>"` next to `default_value` for every entry. Enum:
   - W (power), Wh / kWh (energy)
   - €/kWh, € (price/cost — currency-neutral marker; maintainer uses €)
   - % (percent 0..100), fraction (0..1 — distinct from %)
   - °C (temperature), ° (degrees lat/long/azimuth)
   - min, h, days, timesteps (time)
   - count (dimensionless integer), s (seconds for timeouts)
   - none (booleans/strings/sensor-IDs/method-selectors)
5. Description text NOT touched in this PR (separate concerns).
6. UI render test: docker container boot, browser config page, verify no JS errors.

Verified unit choices for tricky entries (audit 2026-04-28):
- battery_minimum/maximum/target_state_of_charge: fraction (Description says "(percentage/100)")
- battery_dynamic_max/min: fraction per hour
- lp_solver_mip_rel_gap: fraction
- inverter_efficiency_*, alpha, beta: fraction
- nominal_power/min_power deferrable, max_grid_power: W
- battery_nominal_energy_capacity: Wh
- load_peak/offpeak_hours_cost, photovoltaic_production_sell_price, weight_battery_*, inverter/battery_stress_cost: €/kWh
- optimization_time_step, open_meteo_cache_max_age: min
- adjusted_pv_model_max_age: h
- delta_forecast_daily, historic_days_to_retrieve: days
- start/end_timesteps_of_each_deferrable_load, set_deferrable_max_startups: timesteps or count
- operating_hours_of_each_deferrable_load: h
- num_threads, num_lags, number_of_deferrable_loads, *_stress_segments, modules_per_string, strings_per_inverter, influxdb_port: count
- lp_solver_timeout: s
- adjusted_pv_solar_elevation_threshold, surface_tilt, surface_azimuth: °
- type=select / sensor-IDs / method-selectors: none

Backward-compat: consumers using `.get("unit", None)` keep working. Zero-config default not broken.

Account: switch to OptimalNothing90 before push, switch back to mschaepers afterward.

Out of scope (separate cards): AC-2-fix (audit mismatches), AC-2b (runtime params), Description-trim cleanup.

Success criteria: Issue opened + maintainer responded → PR opened with single concern (unit field) → all ~80 entries have unit → UI renders cleanly.""",
        "Status": "Candidates",
        "Category": "Infra",
        "Phase": "Phase 3",
        "Priority": "P1",
        "Effort": "S",
        "Scope": "Upstream",
    },
    {
        "id": "AC-2-fix",
        "title": "AC-2-fix: Correct audit-found mismatches in param_definitions.json",
        "body": """Fix 7 default/type mismatches found during the schema audit that produced AC-2a (unit field) and PR #817 (regression_model typo). Sibling fix-PR — same audit pass, different concern.

Source: schema audit cross-checked param_definitions.json defaults/types vs src/emhass/data/config_defaults.json + utils.treat_runtimeparams (lines ~597-1334).

Confirmed mismatches (re-verify before PR):
- sensor_replace_zero default
- historic_days_to_retrieve default (2 vs 9)
- (full list to be re-derived from audit; schema-audit script can reproduce)

Process: per-mismatch verification against config_defaults.json + utils.treat_runtimeparams, then single PR with clear before/after table in description.

Backward-compat: only correct-the-default fixes — no breaking schema additions. Each mismatch independently verifiable.

Out of scope: AC-2a (unit field, separate concern), AC-2b (runtime params block).

Effort: XS to S depending on how many mismatches survive re-verification.

Account: switch to OptimalNothing90 before push.""",
        "Status": "Ideas",
        "Category": "A: Code-Lifecycle",
        "Phase": "Phase 1",
        "Priority": "P2",
        "Effort": "XS",
        "Scope": "Upstream",
    },
]

# Run updates
print("=== Updating existing card bodies ===")
for item_id, body in NEW_BODIES.items():
    print(f"{item_id}:")
    update_draft(DRAFT_IDS[item_id], body)

print("\n=== Creating new cards ===")
new_item_ids = {}
for item in NEW_ITEMS:
    print(f"{item['id']}:")
    fields = {
        k: item[k]
        for k in ("Status", "Category", "Phase", "Priority", "Effort", "Scope")
    }
    iid = add_draft_with_fields(
        item["title"], item["body"], fields, option_ids, field_ids
    )
    new_item_ids[item["id"]] = iid

# Sync JSON
print("\n=== Syncing items.json ===")
existing_by_id = {it["id"]: it for it in data["items"]}
for item_id, body in NEW_BODIES.items():
    if item_id in existing_by_id:
        existing_by_id[item_id]["body"] = body
        print(f"  body updated for {item_id}")

# Insert new items into JSON in sensible position (after AC-2)
ac2_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AC-2")
for new in reversed(NEW_ITEMS):
    json_entry = {
        "id": new["id"],
        "title": new["title"],
        "type": "draft",
        "body": new["body"],
        "Status": new["Status"],
        "Category": new["Category"],
        "Phase": new["Phase"],
        "Priority": new["Priority"],
        "Effort": new["Effort"],
        "Scope": new["Scope"],
    }
    data["items"].insert(ac2_idx + 1, json_entry)
    print(f"  added {new['id']} to items.json")

with DATA_FILE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"  items.json: {len(data['items'])} items total")

print("\n=== Done ===")
