"""PR #836 bookkeeping (DOC-cookbook → upstream review):
- Add PR-836 as link card to project
- Set PR-836 fields (Status=Review, Category, Phase, Pri, Effort, Scope)
- Move DOC-cookbook board-card Status: In Progress → Review
- Sync items.json

Idempotent guard: skip add_content_to_project if PR-836 already in data["items"].
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DOC_COOKBOOK_BOARD_ID = "DOC-cookbook"
PR_836_NODE_ID = "PR_kwDOGC8VbM7aD00I"
PR_836_NUMBER = 836
PR_836_TITLE = "docs(cookbook): scaffold cookbook section + Node-RED MPC + battery-aware seed recipes"

PR_836_FIELDS = {
    "Status": "Review",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 1.5",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # 1. Move DOC-cookbook Status: In Progress → Review
    item = find_item(data, DOC_COOKBOOK_BOARD_ID)
    assert (
        item["Status"] == "In Progress"
    ), f"unexpected DOC-cookbook Status: {item['Status']}"
    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Review"],
    )
    item["Status"] = "Review"
    print("DOC-cookbook -> Review")

    # 2. Add PR-836 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_836_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_836_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_836_NODE_ID)
        print(f"PR-{PR_836_NUMBER} added: {pr_item_id}")

    # 3. Set PR-836 fields
    for fname, fval in PR_836_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_836_NUMBER} fields: {PR_836_FIELDS}")

    # 4. Sync items.json
    if existing is None:
        cookbook_idx = next(
            i for i, it in enumerate(data["items"]) if it["id"] == DOC_COOKBOOK_BOARD_ID
        )
        pr_entry = {
            "id": f"PR-{PR_836_NUMBER}",
            "title": PR_836_TITLE,
            "type": "link",
            "content_id": PR_836_NODE_ID,
            **PR_836_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_836_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_836_NUMBER,
        }
        data["items"].insert(cookbook_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_836_NUMBER} entry after DOC-cookbook")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
