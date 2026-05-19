"""Post-merge bookkeeping for PR #851, #866, #867 (all merged 2026-05-19 evening).

State after fetch.py refresh on 2026-05-20:
- PR-851 Status auto-synced Review -> Done / Wont Do (AC-3 last-run endpoint)
- PR-866 Status auto-synced Review -> Done / Wont Do (Sonar fork skip, #857)
- PR-867 Status auto-synced Review -> Done / Wont Do (currency sweep, #854)
- AC-3 parent draft still Review -> flip to Done / Wont Do

PR-851 sibling-pairs with AC-3 draft (Case A). PR-866 and PR-867 are standalone
link cards (no parent draft umbrella; fix-PRs for upstream issues #857/#854).

Maintainer-court is now EMPTY.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AC_3_BOARD_ID = "AC-3"


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    item = find_item(data, AC_3_BOARD_ID)
    assert item["Status"] == "Review", f"unexpected AC-3 Status: {item['Status']}"

    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Done / Wont Do"],
    )
    item["Status"] = "Done / Wont Do"
    print(f"{AC_3_BOARD_ID} Status: Review -> Done / Wont Do")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
