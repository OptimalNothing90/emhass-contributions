"""Promote Tier-1 (AC-3, AC-4, AM-1) + Tier-2 (AC-2a) board cards to Status: Todo.

Source: 2026-05-11 backlog triage. Tier-1 = LLM-ready strategic API endpoints +
openapi.json. Tier-2 = AC-2a re-activated from Candidates after the cross-repo-flow
self-test parked it.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# (board_id, expected_current_status)
PROMOTIONS = [
    ("AC-3", "Ideas"),
    ("AC-4", "Ideas"),
    ("AM-1", "Ideas"),
    ("AC-2a", "Candidates"),
]


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    for board_id, expected_status in PROMOTIONS:
        item = find_item(data, board_id)
        actual_status = item["Status"]
        if actual_status != expected_status:
            print(
                f"SKIP {board_id}: status is {actual_status!r}, expected {expected_status!r}"
            )
            continue
        set_field(
            PROJECT_ID,
            item["item_id"],
            field_ids["Status"],
            option_ids["Status"]["Todo"],
        )
        item["Status"] = "Todo"
        print(f"{board_id}: {expected_status} -> Todo")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
