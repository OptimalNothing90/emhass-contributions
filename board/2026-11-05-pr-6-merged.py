#!/usr/bin/env python3
"""2026-11-05: PR #6 merged in OptimalNothing90/emhass-contributions: provider
document gets an optional first_step_start stamp checked against the solve's
grid anchor, every list is length-checked against horizon_steps, the
stale_inputs reason (incl. up to 500 chars of a non-200 body) is in the cycle
result, last_cycle.json, on_cycle_end and flexd/plan/state; Q9 in
docs/ev-requirements.md marked answered by one installation. 411 tests.

Idempotent: marker-guarded appends via lib.append_to_body_idempotent.
"""

from __future__ import annotations

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARKER = "## Merged 2026-11-05"

NOTES = {
    "FLEXD-1": (
        "\n\n## Merged 2026-11-05\n"
        "PR #6: LesIT1's three provider-shape asks on main: optional "
        "first_step_start stamp compared with the solve's grid anchor (skip on "
        "mismatch, both instants in the reason), list length check against "
        "horizon_steps (owned keys exempt), stale reason incl. bounded non-200 "
        "body in last_cycle.json, on_cycle_end and flexd/plan/state. 411 tests. "
        "/simplify, /code-review high, Codex pass; one time-based mqtt test "
        "flaked once. All commitments from the issue #1 replies are on main; "
        "short 'on main' comment to LesIT1 pending.\n"
    ),
    "EPIC-EVCC": (
        "\n\n## Merged 2026-11-05\n"
        "PR #6: Q9 in docs/ev-requirements.md (floor tier) marked answered by "
        "one installation per LesIT1: grid rule on the SOC the plan reaches, "
        "floor energy per cycle from the gap at solve time, house battery first, "
        "X as evcc minSoc, above X solar tier in pv mode. R21 item 3 links it.\n"
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
