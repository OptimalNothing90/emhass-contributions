"""One-shot: move AC-4 board card Status: Todo -> In Progress (cross-repo-flow Phase 5)."""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-4"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)

assert item is not None, f"{BOARD_ID} not found in items.json"
print(f"{BOARD_ID} current Status: {item.get('Status')}")

set_field(
    PROJECT_ID,
    item["item_id"],
    field_ids["Status"],
    option_ids["Status"]["In Progress"],
)
item["Status"] = "In Progress"
save_items(data)
print(f"{BOARD_ID} -> In Progress (saved)")
