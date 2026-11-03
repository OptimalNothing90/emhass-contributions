#!/usr/bin/env python3
"""Publications of 2026-11-04: body notes on FLEXD-1 and EPIC-EVCC.

- FLEXD-1: reply to LesIT1 in OptimalNothing90/emhass-contributions#1
  (own 7-day soak result, one-slot over-delivery finding, port and
  runtime-params-provider commitments without dates, ev-requirements
  revision plan).
- EPIC-EVCC: reply to andig in evcc-io/evcc#29815 (optimizer comparison,
  tiered EV demand as the interface proposal).

Idempotent: marker-guarded appends via lib.append_to_body_idempotent.
"""

from __future__ import annotations

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARKER = "## Published 2026-11-04"

NOTES = {
    "FLEXD-1": (
        "\n\n## Published 2026-11-04\n"
        "Reply to LesIT1 in issue #1 (comment 6618006022): own shadow pilot "
        "21.-27.10. 7/7 days pass; new finding, non-modulating standing demands "
        "over-deliver by one slot (accrual to adoption instant plus ceil in the "
        "semi-continuous branch), fix and test to land on main; compose host "
        "ports to become env vars bound to 127.0.0.1; runtime-params provider "
        "contract (path|url, max_age_s, flexd keys win, stale_inputs instead of "
        "a solve); ev-requirements.md revision per his nine points. No dates "
        "committed. Open: issue for the one-slot finding not yet filed.\n"
    ),
    "EPIC-EVCC": (
        "\n\n## Published 2026-11-04\n"
        "Reply to andig in evcc-io/evcc#29815 (discussioncomment-19385467) on "
        "what the evcc optimizer lacks vs EMHASS: loads as decision variables "
        "are the difference, EMHASS weaker on battery/EV (fixed step, hard "
        "windows, relaxed plan not published, EV only as stationary battery). "
        "Interface ask: evcc exports tiered EV demand (charge_from_grid is "
        "yes/no only), takes a power plan back. Fact-checked against "
        "evcc-io/optimizer HEAD, evcc 0.318.0 automatic mode (#32881) and "
        "EMHASS v0.18.6; Codex second pass. Offered to write the evcc half.\n"
    ),
}


def main() -> int:
    data = load_items()
    for item_id, note in NOTES.items():
        it = find_item(data, item_id)
        changed, body = append_to_body_idempotent(it["draft_id"], MARKER, note)
        it["body"] = body
        print(f"{item_id}: {'appended' if changed else 'already present'}")
    save_items(data)
    print(f"items.json synced ({len(data['items'])} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
