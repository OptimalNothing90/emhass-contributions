"""Post-merge-wave restructure of AC-4, AM-1, AC-2 umbrella + new cards AC-2b, AM-1b.

Triggered after PRs #848/#850/#851/#858/#866/#867 merged 2026-05-19. Card bodies were
verified 2026-04-28 against `6537c47`; current master is `777c792` with 40+ commits of
drift. This restructure:

1. Appends post-merge update notes to AC-4, AM-1, AC-2 umbrella bodies (idempotent
   via marker `<!-- restructure-2026-05-20 -->`).
2. Adds new standalone AC-2b draft card (elevated from AC-2 umbrella sub-item),
   Status=Todo, Effort=M (was S in umbrella; revised up).
3. Adds new AM-1b draft card for runtime-payload-side split, Status=Candidates
   (blocked on AC-2b).

Convention notes for bodies:
- ¤/kWh for machine-readable `unit` fields (Unicode U+00A4 generic currency sign)
- currency/kWh for prose
- Reference last_run.py public API (emhass_version, record/read/is_recent)
- Cite line numbers against current master 777c792 with explicit pin
"""

from lib import (
    add_draft_to_project,
    append_to_body_idempotent,
    find_item,
    load_items,
    save_items,
    set_field,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
MARKER = "<!-- restructure-2026-05-20 -->"


AC4_APPEND = f"""

{MARKER}

## Update 2026-05-20 (post AC-3 / PR #851 merge)

AC-3 (`/api/v1/last-run`) merged 2026-05-19. `src/emhass/last_run.py` now ships a
public API that AC-4 should reuse rather than re-discover:

- `last_run.read(data_path: Path) -> dict | None` — last-run snapshot
- `last_run.is_recent(data_path: Path, max_age_seconds: int) -> bool` — staleness check
- `last_run.emhass_version() -> str` — public version helper

Updated implementation outline (~10-15 LOC in `src/emhass/web_server.py`):

```python
from emhass.last_run import read as last_run_read, emhass_version, is_recent

@app.route("/healthz", methods=["GET"])
async def healthz():
    snap = last_run_read(emhass_conf["data_path"])
    return jsonify({{
        "status": "ok" if snap and snap.get("status") == "ok" else "degraded",
        "boot_ts": app.config.get("boot_ts"),
        "last_run_ts": snap.get("timestamp") if snap else None,
        "last_run_status": snap.get("status") if snap else None,
        "versions": {{
            "emhass": emhass_version(),
            "python": platform.python_version(),
            "cvxpy": cvxpy.__version__,
        }},
    }})
```

State on upstream/master `777c792` (verified 2026-05-20):
- 10 routes in `src/emhass/web_server.py` (added `/api/v1/last-run` at L623 via #851)
- `EMHASS_SCHEMA_VERSION = "1.0"` at `src/emhass/command_line.py:33`
- Boot timestamp not yet stored anywhere; AC-4 plan needs to add a one-line capture
  at `app.before_serving` or equivalent and stash it in `app.config`.

Effort: S (~15 LOC + 1 route + 1 boot-ts capture + minimal test). Dependency on AC-3 now MET.
"""


AM1_APPEND = f"""

{MARKER}

## Update 2026-05-20 — split into AM-1 (this card, config + plan-output) and AM-1b (runtime-payload)

Dependency state post-merge-wave:

- AC-1 ✓ merged (#835): `plan_output_schema.md` + `EMHASS_SCHEMA_VERSION` constant
- AC-2a ✓ merged (#850): `unit` field on all 87 `param_definitions.json` entries
- AC-2b pending (new standalone card): ~30 runtime/MPC params not yet in `param_definitions.json`

**AM-1 (this card) — scope reduced to config + plan-output side.** Generator reads
`param_definitions.json` (post-AC-2a) + `plan_output_schema.md` (post-AC-1) → emits
`openapi.json` covering:

- `/configuration` GET/POST — request body schema from `param_definitions.json`
- `/api/v1/last-run` GET — response schema from `last_run.read()` return shape
- `/action/*` POST — runtime payload as `additionalProperties: true` stub (refined by AM-1b once AC-2b lands)

**AM-1b — runtime-payload side, new standalone card.** Blocked on AC-2b. Regenerates
`openapi.json` to replace `additionalProperties: true` with structured schemas per
`/action/*` variant.

Currency convention (locked per #850 / #867): `unit` field uses `¤/kWh` (Unicode
U+00A4 generic currency sign); prose uses `currency/kWh`.

State on upstream/master `777c792` (verified 2026-05-20):
- 10 routes in `web_server.py` (added `/api/v1/last-run` via #851)
- No `openapi.json`, no `openapi.yaml` in repo
- `EMHASS_SCHEMA_VERSION = "1.0"` at `command_line.py:33`
- `src/emhass/last_run.py` public API: `emhass_version()`, `record()`, `read()`, `is_recent()`

Effort: S (config + plan-output side standalone).
"""


AC2_UMBRELLA_APPEND = f"""

{MARKER}

## Update 2026-05-20 — sub-items state

- AC-2a ✓ merged (#850 + revised via #867). `param_definitions.json` has `unit` field
  on all 87 entries (Unicode U+00A4 `¤/kWh` convention). Currency neutrality swept
  through human-readable surfaces too via #867.
- AC-2-fix ✓ merged (#830 / #845). Default-value mismatches resolved per Option-B
  SoT-hierarchy decision (`param_definitions.json` first, `config_defaults.json`
  aligns).
- **AC-2b** (~30 runtime/MPC params) elevated out of this umbrella to its own Todo
  card with full body. See new standalone AC-2b draft. Effort revised S → M.
"""


AC2B_TITLE = "AC-2b: Add runtime/MPC params to param_definitions.json"
AC2B_BODY = """Extend `src/emhass/static/data/param_definitions.json` with the ~30 runtime/MPC params
currently accepted by `utils.treat_runtimeparams` but not present as schema entries.
These are today documented only in `docs/passing_data.md` prose, parse-feindlich for
openapi.json / Pydantic-model / AI-readable-schema consumers.

Audit at `audits/2026-04-28-param-definitions.md` §4.2 lists the candidates. Sample:
`prediction_horizon`, `soc_init`, `soc_final`, `def_total_hours`, `def_total_timestep`,
`def_start_timestep`, `def_end_timestep`, `prod_price_forecast`, `load_cost_forecast`,
`pv_power_forecast`, `load_power_forecast`, `alpha`, `beta`, `perform_backtest`, etc.

Current state (verified 2026-05-20 against upstream/master `777c792`):

- `param_definitions.json` has 87 entries with `unit` field (post AC-2a / #850).
- `utils.treat_runtimeparams` accepts the ~30 runtime params not yet in the schema.
- `docs/passing_data.md` still the only place they appear; review may have stale lines.

## Deliverable

Extend `param_definitions.json` with one entry per runtime param. Each entry follows the
AC-2a convention:

```json
"<param_name>": {
  "friendly_name": "<readable label>",
  "Description": "<concise text, no €/kWh — use currency/kWh in prose>",
  "input": "<type>",
  "default_value": <value or null>,
  "unit": "<from locked enum: W, Wh, kWh, ¤/kWh, €, %, fraction, °C, °, min, h, days, timesteps, count, s, none>"
}
```

Add a new top-level category in `param_definitions.json` (proposed: `"Runtime"`) OR
extend existing categories where the runtime param is a runtime-override of a
config-time entry (decision to be confirmed with maintainer).

## Unblocks

- AM-1b (openapi.json runtime-payload schemas)
- AM-2 (auto-gen config.md from `param_definitions.json`)

## Maintainer-loop expected

- Description-text wording (concise, locale-neutral, references existing
  `passing_data.md` semantics).
- Decision: which params actually belong in `param_definitions.json` vs. staying
  `passing_data.md`-only by maintainer preference (some may be deemed too transient
  for the structured schema).

## Effort

M (~30 entries × Description text + audit walk + maintainer-loop). Was estimated S
inside the umbrella; revised post-AC-2a learning.

## References

- Issue precedent: #826 (AC-2a)
- Audit: `audits/2026-04-28-param-definitions.md` §4.2
- Predecessor: PR #850 (AC-2a unit field on existing 87 entries)
- Currency convention: PR #867 (`currency/kWh` prose, `¤/kWh` machine-field)
"""


AM1B_TITLE = "AM-1b: openapi.json — runtime-payload schemas for /action/* endpoints"
AM1B_BODY = """Extend AM-1's `openapi.json` with structured request schemas for the `/action/*`
family of EMHASS endpoints. Generated from `param_definitions.json`'s runtime-category
entries (post AC-2b landing).

## Sequencing

Blocked on:
- AM-1 merge (initial `openapi.json` committed with `/action/*` request body as
  `additionalProperties: true` stub).
- AC-2b merge (~30 runtime params added to `param_definitions.json`).

## Deliverable

Update `scripts/generate_openapi.py` (from AM-1) to:

1. Read runtime-category entries from `param_definitions.json` (added by AC-2b).
2. Generate per-`/action/*`-variant request schemas:
   - `perfect-optim`, `dayahead-optim`, `naive-mpc-optim`
   - `publish-data`
   - `forecast-model-fit`, `forecast-model-predict`, `forecast-model-tune`
   - `regressor-model-fit`, `regressor-model-predict`
3. Replace AM-1's `additionalProperties: true` stub with the structured schemas.
4. CI workflow check: re-run script on PR, fail if generated diff != committed file.

## State on upstream/master `777c792` (verified 2026-05-20)

- `/action/*` route registered at `web_server.py:659` via `@app.route("/action/<action_name>", methods=["POST"])`.
- Each `<action_name>` accepts runtime params as JSON body; today no published schema.
- `command_line.py` `set_input_data_dict` is the single entry-point that parses the
  body; runtime-param mapping lives in `utils.treat_runtimeparams`.

## Effort

S (mechanical regen + per-variant schema curation, building on AM-1's generator).
"""


NEW_CARD_FIELDS = {
    "Status": None,  # per-card
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": None,  # per-card
    "Scope": "Upstream",
}


def apply_field(field_ids, option_ids, item_id, field_name, value):
    set_field(PROJECT_ID, item_id, field_ids[field_name], option_ids[field_name][value])


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # ----- Append-updates to existing cards (idempotent via marker) -----
    for card_id, suffix in [
        ("AC-4", AC4_APPEND),
        ("AM-1", AM1_APPEND),
        ("AC-2", AC2_UMBRELLA_APPEND),
    ]:
        card = find_item(data, card_id)
        changed, new_body = append_to_body_idempotent(card["draft_id"], MARKER, suffix)
        if changed:
            card["body"] = new_body
            print(f"{card_id}: body appended ({len(suffix)} chars)")
        else:
            print(f"{card_id}: marker already present — skipping append")

    # ----- New AC-2b card (idempotent re-add guard) -----
    if find_card_safe(data, "AC-2b") is not None:
        print("AC-2b: already in items.json — skipping add")
    else:
        item_id, draft_id = add_draft_to_project(PROJECT_ID, AC2B_TITLE, AC2B_BODY)
        for fname, fval in [
            ("Status", "Todo"),
            ("Category", "Infra"),
            ("Phase", "Phase 3"),
            ("Priority", "P1"),
            ("Effort", "M"),
            ("Scope", "Upstream"),
        ]:
            apply_field(field_ids, option_ids, item_id, fname, fval)
        print(f"AC-2b added: item_id={item_id} draft_id={draft_id}")

        # Insert into items.json after AC-2a anchor
        ac2a_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AC-2a")
        data["items"].insert(
            ac2a_idx + 1,
            {
                "id": "AC-2b",
                "title": AC2B_TITLE,
                "type": "draft",
                "Status": "Todo",
                "Category": "Infra",
                "Phase": "Phase 3",
                "Priority": "P1",
                "Effort": "M",
                "Scope": "Upstream",
                "draft_id": draft_id,
                "item_id": item_id,
                "body": AC2B_BODY,
            },
        )

    # ----- New AM-1b card -----
    if find_card_safe(data, "AM-1b") is not None:
        print("AM-1b: already in items.json — skipping add")
    else:
        item_id, draft_id = add_draft_to_project(PROJECT_ID, AM1B_TITLE, AM1B_BODY)
        for fname, fval in [
            ("Status", "Candidates"),
            ("Category", "Infra"),
            ("Phase", "Phase 3"),
            ("Priority", "P1"),
            ("Effort", "S"),
            ("Scope", "Upstream"),
        ]:
            apply_field(field_ids, option_ids, item_id, fname, fval)
        print(f"AM-1b added: item_id={item_id} draft_id={draft_id}")

        # Insert into items.json after AM-1 anchor
        am1_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AM-1")
        data["items"].insert(
            am1_idx + 1,
            {
                "id": "AM-1b",
                "title": AM1B_TITLE,
                "type": "draft",
                "Status": "Candidates",
                "Category": "Infra",
                "Phase": "Phase 3",
                "Priority": "P1",
                "Effort": "S",
                "Scope": "Upstream",
                "draft_id": draft_id,
                "item_id": item_id,
                "body": AM1B_BODY,
            },
        )

    save_items(data)
    print("=== Done ===")


def find_card_safe(data: dict, item_id: str) -> dict | None:
    return next((it for it in data["items"] if it["id"] == item_id), None)


if __name__ == "__main__":
    main()
