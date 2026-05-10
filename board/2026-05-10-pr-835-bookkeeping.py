"""PR #835 bookkeeping (AC-1 → upstream review):
- Add PR-835 as link card to project
- Set PR-835 fields (Status=Review, Category, Phase, Pri, Effort, Scope)
- Move AC-1 board-card Status: In Progress → Review
- Sync items.json

Idempotent guard: skip add_content_to_project if PR-835 already in data["items"].
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AC_1_BOARD_ID = "AC-1"
PR_835_NODE_ID = "PR_kwDOGC8VbM7aC82z"
PR_835_NUMBER = 835
PR_835_TITLE = "docs(schema): publish plan-output column schema + version constant"

PR_835_FIELDS = {
    "Status": "Review",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "M",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # 1. Move AC-1 Status: In Progress → Review
    ac_1 = find_item(data, AC_1_BOARD_ID)
    assert ac_1["Status"] == "In Progress", f"unexpected AC-1 Status: {ac_1['Status']}"
    set_field(
        PROJECT_ID,
        ac_1["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Review"],
    )
    ac_1["Status"] = "Review"
    print("AC-1 -> Review")

    # 2. Add PR-835 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_835_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_835_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_835_NODE_ID)
        print(f"PR-{PR_835_NUMBER} added: {pr_item_id}")

    # 3. Set PR-835 fields
    for fname, fval in PR_835_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_835_NUMBER} fields: {PR_835_FIELDS}")

    # 4. Sync items.json
    if existing is None:
        ac_1_idx = next(
            i for i, it in enumerate(data["items"]) if it["id"] == AC_1_BOARD_ID
        )
        pr_entry = {
            "id": f"PR-{PR_835_NUMBER}",
            "title": PR_835_TITLE,
            "type": "link",
            "content_id": PR_835_NODE_ID,
            **PR_835_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_835_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_835_NUMBER,
        }
        data["items"].insert(ac_1_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_835_NUMBER} entry after AC-1")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
