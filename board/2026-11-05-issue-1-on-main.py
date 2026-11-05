#!/usr/bin/env python3
"""2026-11-05: third reply to LesIT1 in OptimalNothing90/emhass-contributions#1
(comment 6659452992): PR #6 on main (first_step_start stamp, list length check,
stale reason with non-200 body), relay timing note (write the document before
cycle_offset_s), Q9 in docs/ev-requirements.md. All commitments from the
issue #1 replies are now on main; nothing pending but his first weekly report.

Idempotent: marker-guarded append via lib.append_to_body_idempotent.
"""

from __future__ import annotations

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARKER = "## Published 2026-11-05 (on main)"

NOTES = {
    "FLEXD-1": (
        "\n\n## Published 2026-11-05 (on main)\n"
        "Third reply to LesIT1 in issue #1 (comment 6659452992): PR #6 on main "
        "with the three provider-shape points, relay timing note (document for "
        "the upcoming boundary before cycle_offset_s, else skipped not shifted), "
        "Q9 answered in ev-requirements.md. No open commitments; waiting on his "
        "first weekly shadow report.\n"
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
