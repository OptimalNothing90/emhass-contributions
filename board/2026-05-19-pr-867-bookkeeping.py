"""PR #867 bookkeeping (fix-PR for issue #854 — currency-neutrality sweep Cat 1+2):
- Add PR-867 as standalone link card (no parent board-card; fix-PR for upstream issue #854)
- Set PR-867 fields (Status=Review, Category=Infra, Phase=Phase 3, Pri=P1, Effort=S, Scope=Upstream)
- Sync items.json

21 mechanical €/kWh → currency/kWh replacements across 9 files (spec'd 11; 2 had
no live occurrences). Maintainer pre-approval in #854: Cat 1+2 green-lit, Cat 3
deferred.
"""

from lib import add_content_to_project, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_867_NODE_ID = "PR_kwDOGC8VbM7dPwi_"
PR_867_NUMBER = 867
PR_867_TITLE = (
    "docs(currency): sweep €/kWh → currency/kWh across docs + code comments (#854)"
)

PR_867_FIELDS = {
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

    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_867_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_867_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_867_NODE_ID)
        print(f"PR-{PR_867_NUMBER} added: {pr_item_id}")

    for fname, fval in PR_867_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_867_NUMBER} fields: {PR_867_FIELDS}")

    if existing is None:
        pr_entry = {
            "id": f"PR-{PR_867_NUMBER}",
            "title": PR_867_TITLE,
            "type": "link",
            "content_id": PR_867_NODE_ID,
            **PR_867_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_867_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_867_NUMBER,
        }
        data["items"].append(pr_entry)
        print(f"items.json: appended PR-{PR_867_NUMBER} entry")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
