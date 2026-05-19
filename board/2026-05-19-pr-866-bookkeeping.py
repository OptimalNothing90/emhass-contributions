"""PR #866 bookkeeping (fix-PR for issue #857 — Sonar skip on fork PRs):
- Add PR-866 as standalone link card (no parent board-card; fix-PR for upstream issue #857)
- Set PR-866 fields (Status=Review, Category=Infra, Phase=Phase 3, Pri=P1, Effort=XS, Scope=Upstream)
- Sync items.json

1-line `if:` conditional on SonarQube Scan step in .github/workflows/codecov.yaml.
Maintainer pre-approval in #857: "Yes we can just treat this with option a)".
"""

from lib import add_content_to_project, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_866_NODE_ID = "PR_kwDOGC8VbM7dO46D"
PR_866_NUMBER = 866
PR_866_TITLE = "fix(ci): skip SonarQube Scan on fork PRs (#857)"

PR_866_FIELDS = {
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

    existing = next(
        (it for it in data["items"] if it["id"] == f"PR-{PR_866_NUMBER}"), None
    )
    if existing is not None:
        print(f"PR-{PR_866_NUMBER} already in items.json — skipping add")
        pr_item_id = existing["item_id"]
    else:
        pr_item_id = add_content_to_project(PROJECT_ID, PR_866_NODE_ID)
        print(f"PR-{PR_866_NUMBER} added: {pr_item_id}")

    for fname, fval in PR_866_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_866_NUMBER} fields: {PR_866_FIELDS}")

    if existing is None:
        pr_entry = {
            "id": f"PR-{PR_866_NUMBER}",
            "title": PR_866_TITLE,
            "type": "link",
            "content_id": PR_866_NODE_ID,
            **PR_866_FIELDS,
            "item_id": pr_item_id,
            "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_866_NUMBER}",
            "repository": "davidusb-geek/emhass",
            "number": PR_866_NUMBER,
        }
        data["items"].append(pr_entry)
        print(f"items.json: appended PR-{PR_866_NUMBER} entry")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
