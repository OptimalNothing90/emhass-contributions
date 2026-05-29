"""One-shot: move AM-1 board card Status: Todo -> In Progress (cross-repo-flow Phase 5).

Also corrects AM-2's LOCAL cache fields to the node-query-verified live values: the
GitHub Projects items() list connection is lagging the node() lookup for the just-created
AM-2 draft, so fetch.py writes stale AM-2 fields. Live board is correct (verified). This
is a local-cache fix only — no live mutation for AM-2.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

# --- AM-1: live mutation Todo -> In Progress ---
am1 = find_item(data, "AM-1")
assert am1 is not None, "AM-1 not found"
print(f"AM-1 current Status: {am1.get('Status')}")
set_field(
    PROJECT_ID, am1["item_id"], field_ids["Status"], option_ids["Status"]["In Progress"]
)
am1["Status"] = "In Progress"
print("AM-1 -> In Progress (live + local)")

# --- AM-2: local cache correction only (live already correct, node-verified) ---
am2 = find_item(data, "AM-2")
if am2 is not None:
    am2["Status"] = "Candidates"
    am2["Category"] = "Infra"
    am2["Priority"] = "P2"
    am2["Effort"] = "S"
    print(
        "AM-2 local cache corrected to node-verified values (list-replica lag workaround)"
    )

save_items(data)
print("saved")
