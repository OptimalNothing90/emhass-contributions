"""AC-2a start: move board card Status Todo -> In Progress.

Cross-repo-flow Phase 5. Spec + plan written at 2026-05-14 paths.
Fork-session handoff next.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    item = find_item(data, BOARD_ID)
    assert (
        item["Status"] == "Todo"
    ), f"unexpected AC-2a Status before start: {item['Status']}"

    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["In Progress"],
    )
    item["Status"] = "In Progress"
    print(f"{BOARD_ID} Status: Todo -> In Progress")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
