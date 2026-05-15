"""PR #858 bookkeeping (fix-PR for issue #856 — test_load_deactivation pin):
- Add PR-858 as standalone link card (no parent board-card; fix-PR for issue #856)
- Set PR-858 fields (Status=Review, Category=Infra, Phase=Phase 3, Pri=P1, Effort=XS, Scope=Upstream)
- Sync items.json

1-line test-fixture pin. Fixes regression introduced by our merged PR #845.
"""

from lib import add_content_to_project, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_858_NODE_ID = "PR_kwDOGC8VbM7b21c1"
PR_858_NUMBER = 858
PR_858_TITLE = "fix(test): pin load_forecast_method in test_load_deactivation_zero_operating_timesteps (#856)"

PR_858_FIELDS = {
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

    # 1. Add PR-858 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_858_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_858_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_858_NODE_ID)
        print(f"PR-{PR_858_NUMBER} added: {pr_item_id}")

    # 2. Set PR-858 fields
    for fname, fval in PR_858_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_858_NUMBER} fields: {PR_858_FIELDS}")

    # 3. Sync items.json — append at end (no natural anchor)
    if existing is None:
        pr_entry = {
            "id": f"PR-{PR_858_NUMBER}",
            "title": PR_858_TITLE,
            "type": "link",
            "content_id": PR_858_NODE_ID,
            **PR_858_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_858_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_858_NUMBER,
        }
        data["items"].append(pr_entry)
        print(f"items.json: appended PR-{PR_858_NUMBER} entry")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
