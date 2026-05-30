"""One-shot: AC-2b pr-open bookkeeping (cross-repo-flow Phase 7).

- Add PR #915 sibling 'link' card (Status=Review, Category=A: Code-Lifecycle).
- Move AC-2b source card Status: In Progress -> Review.
All live mutations; items.json synced afterwards via fetch.py.
"""

from lib import add_content_to_project, find_item, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_NODE_ID = "PR_kwDOGC8VbM7g1io9"  # PR #915

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

try:
    find_item(data, "PR-915")
    print("PR-915 already on board - skipping add")
except KeyError:
    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    print(f"added PR #915 card: item={pr_item_id}")
    set_field(
        PROJECT_ID, pr_item_id, field_ids["Status"], option_ids["Status"]["Review"]
    )
    set_field(
        PROJECT_ID,
        pr_item_id,
        field_ids["Category"],
        option_ids["Category"]["A: Code-Lifecycle"],
    )
    print("  set PR-915 Status=Review, Category=A: Code-Lifecycle")

ac2b = find_item(data, "AC-2b")
print(f"AC-2b current Status: {ac2b.get('Status')}")
set_field(
    PROJECT_ID, ac2b["item_id"], field_ids["Status"], option_ids["Status"]["Review"]
)
print("AC-2b -> Review (live)")
print("done")
