"""Create AC-6 = synthesis-N1: GET /api/v1/plan structured plan output.

The one EMHASS-core ask from RFC 0001 (sidecar pivot, #931). Picked as the next build:
it enables every consumer (the registry sidecar + the EV-coupling glue David and the
production users are already designing on #824) to read the plan back machine-readably.

Create-only: items.json catches up on next fetch.py. id 'AC-6' verified free.
"""

from lib import add_draft_to_project, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

TITLE = "AC-6: GET /api/v1/plan structured plan output"
BODY = """\
Synthesis-N1 — the one EMHASS-core ask from RFC 0001 (sidecar pivot, #931).

Add `GET /api/v1/plan`: serialize the latest `opt_res` (computed then discarded at
`web_server.py`, synthesis F11) as JSON records + `emhass_schema_version`, columns per
`docs/plan_output_schema.md` (#835). Read-only, additive, non-breaking. Mirrors
`GET /api/v1/last-run` (#851).

Lets every consumer read the plan back machine-readably instead of scraping the HA
publish or the CSV: the external registry sidecar (RFC 0001), and the EV-coupling glue
people already build (David's #824 Approach 1 "State-Override Bridge"; LesIT1 /
scruysberghs / informatico-madrid production setups).

Serves EPIC-EVCC (enabler) + EPIC-LLM (machine-readable plan). PR-first.
"""

FIELDS = {
    "Status": "Todo",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    if "AC-6" in {i["id"] for i in data["items"]}:
        print("AC-6: already exists — skip")
        return
    item_id, draft_id = add_draft_to_project(PROJECT_ID, TITLE, BODY)
    for k, v in FIELDS.items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    print(f"AC-6 created: item={item_id} draft={draft_id} -> {FIELDS}")
    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
