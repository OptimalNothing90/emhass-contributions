"""Promote 5 non-blocked backlog cards to Status: Todo.

Source: 2026-06-03 backlog triage while EVCC RFC 0001 (#931) awaits resonance.
Selection = next 5 interesting, non-blocked items, goal-weighted:

- AM-7  (Candidates -> Todo): drift-guard test param_definitions <-> config_defaults.
        Regression-prevention for the #875-class bug we shipped via #830; we own it,
        so we are the credible author. Rides alongside #934.
- AM-2  (Ideas -> Todo): auto-generate config.md from schema. LLM-ready + anti-drift;
        param_definitions=SoT already maintainer-green-lit.
- U-6   (Ideas -> Todo): aiohttp.ClientSession without timeout (forecast.py). P0,
        XS goodwill bug. Line must be re-verified vs current upstream before PR.
- U-3   (Ideas -> Todo): Solcast 2xx routed to failure branch (forecast.py). P0, XS.
        Re-verify line before PR.
- ISSUE-807-U-2 (Candidates -> Todo): Dynamic battery charge power by forecasted SoC.
        Existing upstream FR #807; personally relevant (battery in our optim).

EV-9 deliberately EXCLUDED at user request (EVCC direction still under evaluation).

Queuing to Todo != commitment to a blind PR. Per feedback_no_auto_bugfix, the two bug
cards (U-3/U-6) still need explicit go + source-line re-verification before any PR.
"""

from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# (board_id, expected_current_status)
PROMOTIONS = [
    ("AM-7", "Candidates"),
    ("AM-2", "Ideas"),
    ("U-6", "Ideas"),
    ("U-3", "Ideas"),
    ("ISSUE-807-U-2", "Candidates"),
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
