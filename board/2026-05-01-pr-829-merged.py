#!/usr/bin/env python3
"""PR #829 merged upstream (Case B: link-to-issue, no draft umbrella).

Issue #818 was closed by the merge. Bookkeeping:
- ISSUE-818 link card: Status Review -> Done / Wont Do
- PR-829: add as link card, Status = Done / Wont Do, fields mirrored
  from ISSUE-818 (Phase/Priority/Effort/Scope same; Category =
  A: Code-Lifecycle since the PR is the code change)
- items.json: insert PR-829 entry next to ISSUE-818

Idempotent re-add guard: skips creating PR-829 if it already exists in
items.json. Status set is blind (last-writer-wins) so safe to re-run.
"""

from __future__ import annotations

from lib import (
    add_content_to_project,
    find_item,
    load_items,
    save_items,
    set_field,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_829_NODE_ID = "PR_kwDOGC8VbM7W5ieP"
PR_829_URL = "https://github.com/davidusb-geek/emhass/pull/829"
PR_829_TITLE = (
    "fix(utils): wire ignore_pv_feedback_during_curtailment runtime flag (#818)"
)

PR_829_FIELDS = {
    "Status": "Done / Wont Do",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 1",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}


def main() -> int:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    issue = find_item(data, "ISSUE-818")

    print("=== ISSUE-818: Status -> Done / Wont Do ===")
    set_field(
        PROJECT_ID,
        issue["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Done / Wont Do"],
    )
    issue["Status"] = "Done / Wont Do"
    print(f"  ok ({issue['item_id']})")

    try:
        existing = find_item(data, "PR-829")
        print(
            f"\n=== PR-829 already in items.json ({existing['item_id']}) — skipping add ==="
        )
        pr_item_id = existing["item_id"]
    except KeyError:
        print("\n=== PR-829: add link card ===")
        pr_item_id = add_content_to_project(PROJECT_ID, PR_829_NODE_ID)
        for fname, fval in PR_829_FIELDS.items():
            set_field(PROJECT_ID, pr_item_id, field_ids[fname], option_ids[fname][fval])
        print(f"  added {pr_item_id} with fields {PR_829_FIELDS}")

        # Insert into items.json next to ISSUE-818
        idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "ISSUE-818")
        data["items"].insert(
            idx + 1,
            {
                "id": "PR-829",
                "title": PR_829_TITLE,
                "type": "link",
                "content_id": PR_829_NODE_ID,
                **PR_829_FIELDS,
                "item_id": pr_item_id,
                "content_url": PR_829_URL,
                "repository": "davidusb-geek/emhass",
                "number": 829,
            },
        )

    save_items(data)
    print(f"\nitems.json synced ({len(data['items'])} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
