#!/usr/bin/env python3
"""PR #1230 and PR #1229 merged upstream on 2026-10-17 (both Case A).

PR #1230 (docs(cookbook): Node-RED/MQTT/evcc EV charging recipe), umbrella EV-9:
- EV-9 and PR-1230 were already moved to Done / Wont Do on the live board by
  the maintainer (picked up by fetch.py on 2026-10-20). Only the body note is
  added here.

PR #1229 (test: drift guard for config_defaults and param_definitions, by
HFZR2005, offered in #935 on 2026-10-16), umbrella AM-7:
- AM-7: Status Todo -> Done / Wont Do, body note appended.
- PR-1229: add as link card, Status = Done / Wont Do, fields mirrored from
  AM-7 (Infra, Phase 3, P2, S, Upstream).
- items.json: insert PR-1229 entry next to AM-7.

Idempotent: body notes are marker-guarded, PR-1229 add is skipped when the
card already exists, Status sets are last-writer-wins.
"""

from __future__ import annotations

from lib import (
    add_content_to_project,
    append_to_body_idempotent,
    find_item,
    load_items,
    save_items,
    set_field,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

PR_1229_NODE_ID = "PR_kwDOGC8VbM8AAAABI8k8Rw"
PR_1229_URL = "https://github.com/davidusb-geek/emhass/pull/1229"
PR_1229_TITLE = "test: add a drift guard for config_defaults and param_definitions"
PR_1229_FIELDS = {
    "Status": "Done / Wont Do",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P2",
    "Effort": "S",
    "Scope": "Upstream",
}

MARKER = "## Merged 2026-10-17"
EV9_NOTE = (
    "\n\n## Merged 2026-10-17\n"
    "davidusb-geek/emhass#1230 merged by davidusb-geek 2026-10-17 21:16 UTC "
    "(docs/cookbook/ev_evcc_nodered_mqtt.md + index entry). Sourcery left 11 "
    "review points (stale charging state, HTTP status routing, plan reuse after "
    "a failed solve, fractional EV hours on a semi-continuous load); maintainer "
    "approved without changes. Follow-ups, if any, go through a new card.\n"
)
AM7_NOTE = (
    "\n\n## Merged 2026-10-17\n"
    "Shipped by HFZR2005 as davidusb-geek/emhass#1229 (merged 2026-10-17 20:13 "
    "UTC) after the offer in #935. Compares the shared scalar defaults between "
    "param_definitions.json and config_defaults.json in the test suite. "
    "EPIC-REL pillar 2 is covered by it.\n"
)


def main() -> int:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    ev9 = find_item(data, "EV-9")
    print("=== EV-9: body note ===")
    changed, body = append_to_body_idempotent(ev9["draft_id"], MARKER, EV9_NOTE)
    ev9["body"] = body
    print(f"  {'appended' if changed else 'already present'}")

    am7 = find_item(data, "AM-7")
    print("=== AM-7: Status -> Done / Wont Do ===")
    set_field(
        PROJECT_ID,
        am7["item_id"],
        field_ids["Status"],
        option_ids["Status"]["Done / Wont Do"],
    )
    am7["Status"] = "Done / Wont Do"
    print(f"  ok ({am7['item_id']})")
    print("=== AM-7: body note ===")
    changed, body = append_to_body_idempotent(am7["draft_id"], MARKER, AM7_NOTE)
    am7["body"] = body
    print(f"  {'appended' if changed else 'already present'}")

    try:
        existing = find_item(data, "PR-1229")
        print(
            f"=== PR-1229 already in items.json ({existing['item_id']}) — skipping add ==="
        )
    except KeyError:
        print("=== PR-1229: add link card ===")
        pr_item_id = add_content_to_project(PROJECT_ID, PR_1229_NODE_ID)
        for fname, fval in PR_1229_FIELDS.items():
            set_field(PROJECT_ID, pr_item_id, field_ids[fname], option_ids[fname][fval])
        print(f"  added {pr_item_id} with fields {PR_1229_FIELDS}")
        idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AM-7")
        data["items"].insert(
            idx + 1,
            {
                "id": "PR-1229",
                "title": PR_1229_TITLE,
                "type": "link",
                "content_id": PR_1229_NODE_ID,
                **PR_1229_FIELDS,
                "item_id": pr_item_id,
                "content_url": PR_1229_URL,
                "repository": "davidusb-geek/emhass",
                "number": 1229,
            },
        )

    save_items(data)
    print(f"\nitems.json synced ({len(data['items'])} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
