"""AC-3 Status: In Progress -> Todo (park waiting on PR #835 merge).

Fork-session 84234848-1978-48bf-902d-8663f1b6228f stays open + parked per
project_parked_fork_sessions memory. Resume when #835 merges via
`claude --resume 84234848-1978-48bf-902d-8663f1b6228f` from fork repo dir.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-3"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
assert item["Status"] == "In Progress", f"unexpected Status: {item['Status']}"
set_field(
    PROJECT_ID,
    item["item_id"],
    field_ids["Status"],
    option_ids["Status"]["Todo"],
)
item["Status"] = "Todo"
save_items(data)
print("AC-3 -> Todo (parked, fork-session 84234848-1978-48bf-902d-8663f1b6228f open)")
