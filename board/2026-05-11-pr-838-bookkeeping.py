"""PR #838 bookkeeping (AG-onboarding → upstream review):
- Add PR-838 as link card to project
- Set PR-838 fields (Status=Review, Category, Phase, Pri, Effort, Scope)
- Move AG-onboarding board-card Status: In Progress → Review
- Sync items.json

Fork-session 64cc5d1b-28f3-4ad4-9caa-9a8d92606f94 stays resumable for
potential maintainer-style-feedback or sourcery review patches.
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AG_ONBOARDING_BOARD_ID = "AG-onboarding"
PR_838_NODE_ID = "PR_kwDOGC8VbM7aMkVU"
PR_838_NUMBER = 838
PR_838_TITLE = "docs: add develop_ai_coders.md AI-coder contributor onboarding"

PR_838_FIELDS = {
    "Status": "Review",
    "Category": "B: End-User-Ops",
    "Phase": "Phase 1.5",
    "Priority": "P1",
    "Effort": "M",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # 1. Move AG-onboarding Status: In Progress → Review
    item = find_item(data, AG_ONBOARDING_BOARD_ID)
    assert (
        item["Status"] == "In Progress"
    ), f"unexpected AG-onboarding Status: {item['Status']}"
    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Review"],
    )
    item["Status"] = "Review"
    print("AG-onboarding -> Review")

    # 2. Add PR-838 link card (idempotent guard)
    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_838_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_838_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_838_NODE_ID)
        print(f"PR-{PR_838_NUMBER} added: {pr_item_id}")

    # 3. Set PR-838 fields
    for fname, fval in PR_838_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_838_NUMBER} fields: {PR_838_FIELDS}")

    # 4. Sync items.json
    if existing is None:
        ag_idx = next(
            i
            for i, it in enumerate(data["items"])
            if it["id"] == AG_ONBOARDING_BOARD_ID
        )
        pr_entry = {
            "id": f"PR-{PR_838_NUMBER}",
            "title": PR_838_TITLE,
            "type": "link",
            "content_id": PR_838_NODE_ID,
            **PR_838_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_838_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_838_NUMBER,
        }
        data["items"].insert(ag_idx + 1, pr_entry)
        print(f"items.json: inserted PR-{PR_838_NUMBER} entry after AG-onboarding")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
