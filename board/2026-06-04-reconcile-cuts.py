"""Reconcile cuts (2026-06-04): move 4 speculative cards to Done / Wont Do and
de-reference the cut AC-8 from AG-4's body.

Per spec docs/superpowers/specs/2026-06-04-board-strategy-reconcile-design.md §A.
AG-9 is NOT touched here — it has no AC-8 reference (only AG-4 does). AG-9, CE-7,
AM-4, AM-5 are kept (not cut).
"""

from lib import (
    fetch_live_draft,
    find_item,
    load_items,
    save_items,
    set_field,
    update_draft_body,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# (board_id, expected_current_status)
CUTS = [
    ("AM-6", "Ideas"),
    ("AM-3", "Ideas"),
    ("AG-5", "Ideas"),
    ("AC-8", "Ideas"),
]

AC8_CLAUSE = " Demos value of structured error catalog (AC-8)."
AC8_REPLACEMENT = " Inline hints, standalone (no external error catalog)."


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    wontdo = option_ids["Status"]["Done / Wont Do"]

    for board_id, expected in CUTS:
        item = find_item(data, board_id)
        if item["Status"] != expected:
            print(f"SKIP {board_id}: status {item['Status']!r}, expected {expected!r}")
            continue
        set_field(PROJECT_ID, item["item_id"], field_ids["Status"], wontdo)
        item["Status"] = "Done / Wont Do"
        print(f"{board_id}: {expected} -> Done / Wont Do")

    # De-reference AC-8 from AG-4 (fetch live body first; idempotent on the clause)
    ag4 = find_item(data, "AG-4")
    live = fetch_live_draft(ag4["draft_id"])
    body = live.get("body") or ""
    if AC8_CLAUSE in body:
        new_body = body.replace(AC8_CLAUSE, AC8_REPLACEMENT)
        update_draft_body(ag4["draft_id"], new_body)
        ag4["body"] = new_body
        print("AG-4: de-referenced AC-8")
    else:
        print("AG-4: AC-8 clause not present (already de-referenced?) — skip")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
