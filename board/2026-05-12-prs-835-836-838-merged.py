"""Board bookkeeping for 3 PRs merged by davidusb-geek on 2026-05-12:
- PR #835 (AC-1 plan-output schema doc + EMHASS_SCHEMA_VERSION)
- PR #836 (DOC-cookbook scaffold + Node-RED MPC + battery-aware seed recipes)
- PR #838 (AG-onboarding AI-coder contributor doc)

Maintainer automation already moved the 3 PR-link cards (PR-835, PR-836, PR-838)
to Status=Done / Wont Do. This script moves the 3 draft umbrella cards
(AC-1, DOC-cookbook, AG-onboarding) per Case A pattern.

All 3 are Case A (draft umbrella + PR-sibling-link). Idempotent: re-running
skips already-Done cards.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

DRAFT_CARDS = [
    ("AC-1", 835),
    ("DOC-cookbook", 836),
    ("AG-onboarding", 838),
]


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    for board_id, pr_number in DRAFT_CARDS:
        item = find_item(data, board_id)
        current = item.get("Status")
        if current == "Done / Wont Do":
            print(f"{board_id}: already 'Done / Wont Do' — skip (idempotent)")
            continue
        set_field(
            PROJECT_ID,
            item["item_id"],
            field_ids["Status"],
            option_ids["Status"]["Done / Wont Do"],
        )
        item["Status"] = "Done / Wont Do"
        print(f"{board_id}: Review -> Done / Wont Do (merged via PR #{pr_number})")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
