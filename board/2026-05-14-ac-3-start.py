"""AC-3 resume: move board card Status Todo -> In Progress.

Parked fork-session 84234848-1978-48bf-902d-8663f1b6228f resumes.
PR #835 merged 2026-05-12 -> EMHASS_SCHEMA_VERSION on master,
AC-3 pre-flight P3 gate now passes.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-3"


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    item = find_item(data, BOARD_ID)
    assert (
        item["Status"] == "Todo"
    ), f"unexpected AC-3 Status before resume: {item['Status']}"

    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["In Progress"],
    )
    item["Status"] = "In Progress"
    print(f"{BOARD_ID} Status: Todo -> In Progress (resumed)")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
