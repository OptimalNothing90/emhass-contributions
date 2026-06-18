"""Start AC-6 (GET /api/v1/plan): Status Todo -> In Progress.

Spec + plan written, handoff-prompt appended. Fork session about to build the PR.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-6"


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    item = find_item(data, BOARD_ID)
    if item["Status"] == "In Progress":
        print(f"{BOARD_ID}: already In Progress — skip")
        return
    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["In Progress"],
    )
    item["Status"] = "In Progress"
    save_items(data)
    print(f"{BOARD_ID}: Todo -> In Progress")


if __name__ == "__main__":
    main()
