"""Board bookkeeping: flexd e2e smoke green against EMHASS v0.18.6, remaining review findings closed (2026-10-17).

Run from board/ as OptimalNothing90 after `python fetch.py` showed 0 drift. Idempotent (marker guard).
"""

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARK = "## Status 2026-10-17 (evening)"

data = load_items()


def note(card_id: str, text: str) -> None:
    card = find_item(data, card_id)
    changed, body = append_to_body_idempotent(
        card["draft_id"], MARK, f"\n\n{MARK}\n{text}"
    )
    card["body"] = body
    print(f"{card_id}: {'appended' if changed else 'unchanged (marker present)'}")


note(
    "FLEXD-1",
    "Third and fourth batch on main: Mediums 2, 3, 7, 8, 9, 10, 12 and the Lows (2834d7c..e37b9a7), "
    "compose pinned to v0.18.6 with a real-solve e2e smoke (cc4fa0d, db0c96f), and the e2e findings fixed "
    "(327a4fa whole-slot hours instead of operating_timesteps because upstream zeroes hours when that key is "
    "present; e5ed6d4 first record served up to one step early and cycles fire just after the grid boundary; "
    "9142760 EMHASS 4xx reported as rejected). Unit suite 287, e2e smoke against EMHASS v0.18.6 all PASS incl. "
    "modulating 1800 Wh. Review list from issue #1 is closed except Medium 11 (partly) and five un-enumerated Lows. "
    "Shadow run with LesIT1 can start.",
)
note(
    "EPIC-EVCC",
    "RFC 0001 sharpened as lifecycle layer with seven acceptance criteria (d35afd0); docs/ev-requirements.md with "
    "20 requirements as input to multi-battery phase 2 (2a7d9e0). flexd e2e green against v0.18.6; shadow run can start.",
)
note(
    "DISC-1157",
    "Draft +1 for the dry_run split with the flexd use case prepared; posting pending.",
)
note(
    "DISC-1150",
    "docs/ev-requirements.md written (20 requirements, 8 open questions) as phase 2 input; offered to LesIT1 in the #931 draft.",
)

save_items(data)
print("items.json saved")
