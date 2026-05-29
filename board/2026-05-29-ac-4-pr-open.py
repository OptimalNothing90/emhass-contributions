"""One-shot: AC-4 pr-open bookkeeping (cross-repo-flow Phase 7).

- Add PR #914 as a sibling 'link' card (Status=Review, Category=A: Code-Lifecycle,
  matching the existing PR-card convention).
- Move the AC-4 source card Status: In Progress -> Review.

All live mutations; items.json synced afterwards via fetch.py. (PR card + any newly
touched item may lag in the items() list connection; correct locally if so.)
"""

from lib import add_content_to_project, find_item, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_NODE_ID = "PR_kwDOGC8VbM7goKpN"  # PR #914 (gh pr view 914 --json id)

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

# idempotency guard: skip add if PR-914 already on the board
try:
    find_item(data, "PR-914")
    already = True
except KeyError:
    already = False

if already:
    print("PR-914 already on board — skipping add")
else:
    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    print(f"added PR #914 card: item={pr_item_id}")
    set_field(
        PROJECT_ID, pr_item_id, field_ids["Status"], option_ids["Status"]["Review"]
    )
    set_field(
        PROJECT_ID,
        pr_item_id,
        field_ids["Category"],
        option_ids["Category"]["A: Code-Lifecycle"],
    )
    print("  set PR-914 Status=Review, Category=A: Code-Lifecycle")

# AC-4 source card -> Review
ac4 = find_item(data, "AC-4")
assert ac4 is not None, "AC-4 not found"
print(f"AC-4 current Status: {ac4.get('Status')}")
set_field(
    PROJECT_ID, ac4["item_id"], field_ids["Status"], option_ids["Status"]["Review"]
)
print("AC-4 -> Review (live)")
print("done")
