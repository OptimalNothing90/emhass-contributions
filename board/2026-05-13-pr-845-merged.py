"""PR #845 merged 2026-05-13 08:32:26 UTC — Case A bookkeeping.

PR #845 was the Option-B follow-up to #830 (config_defaults.json align with
param_definitions.json). The umbrella AC-2-fix card was already Done / Wont Do
from earlier bookkeeping. PR-845 link card was not added to board at PR-open
time (oversight); this script adds it now with Status=Done / Wont Do directly.

Idempotent: skips if PR-845 already in items.json.
"""

from lib import add_content_to_project, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_NUMBER = 845
PR_NODE_ID = "PR_kwDOGC8VbM7a1wql"
PR_TITLE = "fix(config): align config_defaults.json with param_definitions.json per #830 Option-B decision"

PR_FIELDS = {
    "Status": "Done / Wont Do",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 1",
    "Priority": "P2",
    "Effort": "XS",
    "Scope": "Upstream",
}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    existing = next((it for it in data["items"] if it["id"] == f"PR-{PR_NUMBER}"), None)
    if existing is not None:
        print(f"PR-{PR_NUMBER} already in items.json — skipping add")
        return

    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    print(f"PR-{PR_NUMBER} added to project: {pr_item_id}")

    for fname, fval in PR_FIELDS.items():
        set_field(
            PROJECT_ID,
            pr_item_id,
            field_ids[fname],
            option_ids[fname][fval],
        )
    print(f"PR-{PR_NUMBER} fields set: {PR_FIELDS}")

    # Insert PR-845 entry after PR-830 (its sibling in AC-2-fix umbrella)
    pr_830_idx = next(
        (i for i, it in enumerate(data["items"]) if it["id"] == "PR-830"), None
    )
    insert_idx = (pr_830_idx + 1) if pr_830_idx is not None else len(data["items"])

    pr_entry = {
        "id": f"PR-{PR_NUMBER}",
        "title": PR_TITLE,
        "type": "link",
        "content_id": PR_NODE_ID,
        **PR_FIELDS,
        "item_id": pr_item_id,
        "content_url": f"https://github.com/davidusb-geek/emhass/pull/{PR_NUMBER}",
        "repository": "davidusb-geek/emhass",
        "number": PR_NUMBER,
    }
    data["items"].insert(insert_idx, pr_entry)
    print(f"items.json: inserted PR-{PR_NUMBER} after PR-830 (idx {insert_idx})")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
