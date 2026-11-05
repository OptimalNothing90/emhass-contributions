#!/usr/bin/env python3
"""2026-11-05: second reply to LesIT1 in OptimalNothing90/emhass-contributions#1
(comment 6653335393): PRs #2/#3/#5 on main with env names and links, his three
provider-shape asks accepted as "lands on main" (first-step stamp, length check
vs prediction_horizon, stale reason plus non-200 body in the cycle result),
floor-tier rule goes into docs/ev-requirements.md, recommendation to start the
shadow on current main rather than caf9ee4. Work started in its own session.

Idempotent: marker-guarded append via lib.append_to_body_idempotent.
"""

from __future__ import annotations

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARKER = "## Published 2026-11-05"

NOTES = {
    "FLEXD-1": (
        "\n\n## Published 2026-11-05\n"
        "Reply to LesIT1 in issue #1 (comment 6653335393): #2/#3/#5 on main "
        "with env names and PR links; his three provider-shape asks accepted, "
        "to land on main (first-step stamp, list-length check against "
        "prediction_horizon, stale reason plus bounded non-200 body in the "
        "cycle result); floor-tier rule to be written into ev-requirements.md; "
        "recommended starting the shadow on current main. No dates committed. "
        "Provider v2 + doc update in progress in a separate session.\n"
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
