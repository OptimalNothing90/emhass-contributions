"""Post-merge bookkeeping for PR #848, #850, #858 (all merged 2026-05-19).

State after fetch.py refresh on 2026-05-19:
- PR-848 Status auto-synced Review -> Done / Wont Do
- PR-850 Status auto-synced Review -> Done / Wont Do
- PR-858 Status auto-synced Review -> Done / Wont Do
- AC-2a parent draft still Review -> flip to Done / Wont Do
- AC-3 stays Review (PR-851 still open, awaiting rebase + test fixes per
  maintainer comment 2026-05-19 14:14)

PR-848 and PR-858 are standalone link cards (no parent draft umbrella).
PR-850 sibling-pairs with AC-2a draft (Case A).

Issues #855 #856 #857 not on board (no ISSUE-cards added during filing).
No card-flips needed for issue closures.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AC_2A_BOARD_ID = "AC-2a"


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # Flip AC-2a Status: Review -> Done / Wont Do (PR-850 merged)
    item = find_item(data, AC_2A_BOARD_ID)
    assert item["Status"] == "Review", f"unexpected AC-2a Status: {item['Status']}"

    set_field(
        PROJECT_ID,
        item["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Done / Wont Do"],
    )
    item["Status"] = "Done / Wont Do"
    print(f"{AC_2A_BOARD_ID} Status: Review -> Done / Wont Do")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
