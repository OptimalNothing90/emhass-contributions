"""Card the openapi follow-up: PR #945 (LesIT1's one-time regen) + AM-1c (our planned
systemic auto-regen work-item).

Create-only: items.json catches up on next fetch.py. ids AM-1c / PR-945 verified free.
AM-1c = our planned follow-up to AM-1 (#921 generator+drift-check) → AM-1b (runtime
payloads) → AM-1c (auto-regen so the committed spec can't go stale). Member of EPIC-LLM.
Gated on #945 merge (build on green master).
"""

from lib import add_content_to_project, add_draft_to_project, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

AM1C_TITLE = "AM-1c: openapi.json auto-regen (pre-commit/CI)"
AM1C_BODY = """\
Close the loop on AM-1's committed-vs-generated drift-check (#921): instead of a test that
merely *fails* when `param_definitions.json` changes without a regen, add an **automated
regen** — a pre-commit hook and/or CI step running `scripts/generate_openapi.py` that
fails-or-auto-commits on diff. Removes the recurring "forgot to regen" footgun.

## Why
The drift-check is firing repeatedly: #934 (#875 5000-restore) + delta_forecast_daily +
#373/#939 left `openapi.json` stale → master red → manual regen (#945, LesIT1). #947 + #948
(both edit `param_definitions.json` without regen) will re-break it. Second drift incident
of this class (cf. AM-7 param_def↔config_defaults).

## Lineage / fit
AM-1 (#921, generator + drift-check, merged) → AM-1b (runtime payloads) → AM-1c (this).
Member of EPIC-LLM (single schema → many surfaces, kept in sync).

## Sequencing
Gated on #945 merge — build on a green master, avoid colliding with the open wave.
We added the generator in #921, so we are the credible author for the regen half.
"""
AM1C_FIELDS = {
    "Status": "Candidates",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}

PR945_NODE = "PR_kwDOGC8VbM7jiHFr"
PR945_FIELDS = {
    "Status": "Review",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "XS",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    existing = {i["id"] for i in data["items"]}

    if "AM-1c" in existing:
        print("AM-1c: already exists — skip")
    else:
        item_id, draft_id = add_draft_to_project(PROJECT_ID, AM1C_TITLE, AM1C_BODY)
        for k, v in AM1C_FIELDS.items():
            set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
        print(f"AM-1c created: item={item_id} draft={draft_id} -> {AM1C_FIELDS}")

    if "PR-945" in existing:
        print("PR-945: already carded — skip")
    else:
        item_id = add_content_to_project(PROJECT_ID, PR945_NODE)
        for k, v in PR945_FIELDS.items():
            set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
        print(f"PR-945 linked: item={item_id} -> {PR945_FIELDS}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
