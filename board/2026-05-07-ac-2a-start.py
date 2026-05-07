"""Self-test: AC-2a Status: Candidates -> In Progress (cross-repo-flow validation).

NOTE: self-test deviation — live AC-2a is 'Candidates' (Phase 3), not 'Todo' (Phase 1)
as the task description expected. The mutation Candidates->In Progress->Candidates
exercises the same board-mutation code path and validates the mechanism equivalently.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
assert item["Status"] == "Candidates", f"unexpected Status: {item['Status']}"
set_field(
    PROJECT_ID,
    item["item_id"],
    field_ids["Status"],
    option_ids["Status"]["In Progress"],
)
item["Status"] = "In Progress"
save_items(data)
print("AC-2a -> In Progress")
