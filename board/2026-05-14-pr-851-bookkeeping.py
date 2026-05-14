"""PR #851 bookkeeping (AC-3 /api/v1/last-run JSON endpoint):
- Add PR-851 as link card to project
- Set PR-851 fields (Status=Review, Category=Infra, Phase, Pri, Effort, Scope)
- Move AC-3 board-card Status: In Progress -> Review
- Sync items.json

Fork-session 84234848-1978-48bf-902d-8663f1b6228f stays resumable.
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AC_3_BOARD_ID = "AC-3"
PR_851_NODE_ID = "PR_kwDOGC8VbM7br14x"
PR_851_NUMBER = 851
PR_851_TITLE = "feat(api): add GET /api/v1/last-run JSON endpoint (AC-3)"

PR_851_FIELDS = {
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

    # 1. Move AC-3 Status: In Progress -> Review
    item = find_item(data, AC_3_BOARD_ID)
    assert item["Status"] == "In Progress", f"unexpected AC-3 Status: {item['Status']}"
    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Review"],
    )
    item["Status"] = "Review"
    print("AC-3 -> Review")

    # 2. Add PR-851 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_851_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_851_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_851_NODE_ID)
        print(f"PR-{PR_851_NUMBER} added: {pr_item_id}")

    # 3. Set PR-851 fields
    for fname, fval in PR_851_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_851_NUMBER} fields: {PR_851_FIELDS}")

    # 4. Sync items.json — insert after AC-3
    if existing is None:
        ac_3_idx = next(
            i for i, it in enumerate(data["items"]) if it["id"] == AC_3_BOARD_ID
        )
        pr_entry = {
            "id": f"PR-{PR_851_NUMBER}",
            "title": PR_851_TITLE,
            "type": "link",
            "content_id": PR_851_NODE_ID,
            **PR_851_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_851_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_851_NUMBER,
        }
        data["items"].insert(ac_3_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_851_NUMBER} entry after AC-3")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
