"""PR #848 bookkeeping (Doc-followup: SoT-hierarchy + AI-coder behavioral guardrails):
- Add PR-848 as link card to project (no parent board-card; standalone)
- Set PR-848 fields (Status=Review, Category, Phase, Pri, Effort, Scope)
- Sync items.json

Bundle: SoT-hierarchy capture (PR #845 follow-up, maintainer pre-approved) +
new AGENTS.md Section 6 distilling Karpathy LLM-coding-pitfalls observations.
"""

from lib import add_content_to_project, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_848_NODE_ID = "PR_kwDOGC8VbM7bUa5C"
PR_848_NUMBER = 848
PR_848_TITLE = "docs: capture default-values SoT + add AI-coder behavioral guardrails"

PR_848_FIELDS = {
    "Status": "Review",
    "Category": "B: End-User-Ops",
    "Phase": "Phase 1.5",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # 1. Add PR-848 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_848_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_848_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_848_NODE_ID)
        print(f"PR-{PR_848_NUMBER} added: {pr_item_id}")

    # 2. Set PR-848 fields
    for fname, fval in PR_848_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_848_NUMBER} fields: {PR_848_FIELDS}")

    # 3. Sync items.json — insert after PR-845
    if existing is None:
        pr_845_idx = next(
            i for i, it in enumerate(data["items"]) if it["id"] == "PR-845"
        )
        pr_entry = {
            "id": f"PR-{PR_848_NUMBER}",
            "title": PR_848_TITLE,
            "type": "link",
            "content_id": PR_848_NODE_ID,
            **PR_848_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_848_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_848_NUMBER,
        }
        data["items"].insert(pr_845_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_848_NUMBER} entry after PR-845")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
