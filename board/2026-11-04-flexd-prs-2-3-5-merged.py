#!/usr/bin/env python3
"""Merges of 2026-11-04 in OptimalNothing90/emhass-contributions: body notes on
FLEXD-1 and EPIC-EVCC.

- PR #2 (37af04b): docs/ev-requirements.md revised as modelling contract
  (tiers, import cap, per-source staleness) per LesIT1's nine points.
- PR #5 (d62c6ec): one-slot over-delivery fix (closes #4), compose host ports
  as env vars bound to 127.0.0.1, smoke script on compose port variables.
- PR #3 (bdcca64): runtime-params provider (path|url, max_age_s), read before
  every solve, stale_inputs instead of a solve.
- LesIT1 replied in issue #1 (run not started yet, three provider-shape asks:
  first-step stamp, length check vs prediction_horizon, reason/body in cycle
  result; floor-tier rule answered).

Idempotent: marker-guarded appends via lib.append_to_body_idempotent.
"""

from __future__ import annotations

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARKER = "## Merged 2026-11-04"

NOTES = {
    "FLEXD-1": (
        "\n\n## Merged 2026-11-04\n"
        "Follow-ups from the issue #1 reply are on main: PR #5 (d62c6ec) one-slot "
        "over-delivery fix, closes #4 (residual below 5 min or half a slot no "
        "longer rounds up), compose ports as env vars on 127.0.0.1, smoke script "
        "on compose port vars; PR #3 (bdcca64) runtime-params provider "
        "(path|url, max_age_s default 900, provider wins over static dict, "
        "stale_inputs skips the cycle, visible on last_cycle.json, plan/state, "
        "/simple/status). 386 tests. Each PR went through /simplify, "
        "/code-review high and a Codex pass in its own session. "
        "LesIT1 (issue #1, 2026-11-04): shadow run not started yet, bundle at "
        "caf9ee4, asks for a first-step stamp, list-length check against "
        "prediction_horizon and the stale reason plus non-200 body in the cycle "
        "result; none of the three in #3. Reply with status and commitment "
        "pending.\n"
    ),
    "EPIC-EVCC": (
        "\n\n## Merged 2026-11-04\n"
        "PR #2 (37af04b): docs/ev-requirements.md rewritten as the modelling "
        "contract per LesIT1's nine points (tiers with grid eligibility replace "
        "the single departure target, soc_target collision, p_min, shared import "
        "cap, staleness per source, limitSoc/vehicleSoc 0 semantics, evcc plans "
        "as inputs only, executor concerns moved to RFC 0001). LesIT1 answered "
        "the floor-tier question: grid allowed up to X on the SOC the plan "
        "reaches, floor energy sized per cycle from the gap at solve time, house "
        "battery first, X mirrored as evcc minSoc, above X solar tier in pv mode. "
        "To be written into the doc. andig has not replied in evcc #29815.\n"
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
