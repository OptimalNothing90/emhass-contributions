"""PR #850 bookkeeping (AC-2a unit field):
- Add PR-850 as link card to project
- Set PR-850 fields (Status=Review, Category=Infra, Phase, Pri, Effort, Scope)
- Move AC-2a board-card Status: In Progress -> Review
- Sync items.json
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AC_2A_BOARD_ID = "AC-2a"
PR_850_NODE_ID = "PR_kwDOGC8VbM7broFS"
PR_850_NUMBER = 850
PR_850_TITLE = "feat(schema): add unit field to param_definitions.json (#826)"

PR_850_FIELDS = {
    "Status": "Review",
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

    # 1. Move AC-2a Status: In Progress -> Review
    item = find_item(data, AC_2A_BOARD_ID)
    assert item["Status"] == "In Progress", f"unexpected AC-2a Status: {item['Status']}"
    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Review"],
    )
    item["Status"] = "Review"
    print("AC-2a -> Review")

    # 2. Add PR-850 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_850_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_850_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_850_NODE_ID)
        print(f"PR-{PR_850_NUMBER} added: {pr_item_id}")

    # 3. Set PR-850 fields
    for fname, fval in PR_850_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_850_NUMBER} fields: {PR_850_FIELDS}")

    # 4. Sync items.json — insert after AC-2a
    if existing is None:
        ac_2a_idx = next(
            i for i, it in enumerate(data["items"]) if it["id"] == AC_2A_BOARD_ID
        )
        pr_entry = {
            "id": f"PR-{PR_850_NUMBER}",
            "title": PR_850_TITLE,
            "type": "link",
            "content_id": PR_850_NODE_ID,
            **PR_850_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_850_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_850_NUMBER,
        }
        data["items"].insert(ac_2a_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_850_NUMBER} entry after AC-2a")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
