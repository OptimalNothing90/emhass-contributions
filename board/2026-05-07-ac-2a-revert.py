"""Self-test rollback: AC-2a Status: In Progress -> Candidates.

NOTE: self-test deviation — live AC-2a was 'Candidates' before self-test,
so this reverts to 'Candidates' (not 'Todo' as the task stub assumed).
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
assert item["Status"] == "In Progress"
set_field(
    PROJECT_ID, item["item_id"], field_ids["Status"], option_ids["Status"]["Candidates"]
)
item["Status"] = "Candidates"
save_items(data)
print("AC-2a -> Candidates (reverted)")
