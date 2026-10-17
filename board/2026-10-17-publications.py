"""Board bookkeeping: publications of 2026-10-17 (Mauricio's go).

Posted: discussion #1157 (+1 dry_run split), discussion #931 (RFC 0001 update), issue #1 reply
(shadow run released), draft PR #1230 (EV-9 cookbook recipe), issues #1231 (AC-2c) and #1232
(AM-1b), comment on #1106 (U-1 analysis).

Run from board/ as OptimalNothing90 after `python fetch.py` showed 0 drift. Idempotent.
"""

from lib import (
    add_content_to_project,
    append_to_body_idempotent,
    find_item,
    gh_graphql,
    load_items,
    save_items,
    set_field,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
MARK = "## Published 2026-10-17"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]


def status(card_id: str, value: str) -> None:
    card = find_item(data, card_id)
    set_field(
        PROJECT_ID, card["item_id"], field_ids["Status"], option_ids["Status"][value]
    )
    card["Status"] = value
    print(f"{card_id} -> {value}")


def note(card_id: str, text: str) -> None:
    card = find_item(data, card_id)
    changed, body = append_to_body_idempotent(
        card["draft_id"], MARK, f"\n\n{MARK}\n{text}"
    )
    card["body"] = body
    print(f"  {card_id}: body {'appended' if changed else 'unchanged'}")


def node_id(kind: str, number: int) -> dict:
    q = f'{{ repository(owner:"davidusb-geek", name:"emhass") {{ {kind}(number:{number}) {{ id url title }} }} }}'
    return gh_graphql(q)["data"]["repository"][kind]


def add_link(card_id: str, after: str, kind: str, number: int, fields: dict) -> None:
    try:
        find_item(data, card_id)
        print(f"{card_id} already present")
        return
    except KeyError:
        pass
    content = node_id(kind, number)
    item_id = add_content_to_project(PROJECT_ID, content["id"])
    for k, v in fields.items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    idx = next(i for i, it in enumerate(data["items"]) if it["id"] == after)
    data["items"].insert(
        idx + 1,
        {
            "id": card_id,
            "title": content["title"],
            "type": "link",
            "content_id": content["id"],
            **fields,
            "item_id": item_id,
            "content_url": content["url"],
            "repository": "davidusb-geek/emhass",
            "number": number,
        },
    )
    print(f"{card_id} link card added -> {fields['Status']}")


# EV-9: draft PR #1230 open -> draft card Done (runbook case A), PR card Review
note(
    "EV-9",
    "Draft PR davidusb-geek/emhass#1230 opened 2026-10-17 from fork branch docs/ev-9-nodered-mqtt-evcc-recipe. "
    "Gates before ready: CI, CodeQL, bot review answered, self-review, out-of-scope check.",
)
status("EV-9", "Done / Wont Do")
add_link(
    "PR-1230",
    "EV-9",
    "pullRequest",
    1230,
    {
        "Status": "Review",
        "Category": "B: End-User-Ops",
        "Phase": "Phase 4",
        "Priority": "P0",
        "Effort": "M",
        "Scope": "Upstream",
    },
)

# AC-5 stays In Progress; opens after #1230 lands (one PR at a time)
note(
    "AC-5",
    "Branch ready; PR opens after #1230 is merged or the maintainer's next wave (no PR bursts).",
)

# AC-2c / AM-1b: issue-first posted
note(
    "AC-2c",
    "Issue-first proposal posted as davidusb-geek/emhass#1231 (three options, recommendation: entries in runtime_params.json). Awaiting maintainer.",
)
add_link(
    "ISSUE-1231",
    "AC-2c",
    "issue",
    1231,
    {
        "Status": "Candidates",
        "Category": "Infra",
        "Phase": "Phase 3",
        "Priority": "P1",
        "Effort": "M",
        "Scope": "Upstream",
    },
)
note(
    "AM-1b",
    "Issue-first proposal posted as davidusb-geek/emhass#1232 (three options, recommendation: generated RuntimeParams component plus action_name enum). Awaiting maintainer.",
)
add_link(
    "ISSUE-1232",
    "AM-1b",
    "issue",
    1232,
    {
        "Status": "Candidates",
        "Category": "Infra",
        "Phase": "Phase 3",
        "Priority": "P1",
        "Effort": "S",
        "Scope": "Upstream",
    },
)

# Discussions
note(
    "DISC-1157",
    "Posted 2026-10-17: +1 for the dry_run split with the flexd what-if use case, two contract points (unknown flag must not run live, actions that cannot honour it reject it).",
)
status("DISC-1157", "In Progress")
note(
    "DISC-1150",
    "Offered docs/ev-requirements.md to LesIT1 as phase 2 input in the #931 update (2026-10-17).",
)
status("DISC-1150", "In Progress")
note(
    "EPIC-EVCC",
    "RFC 0001 update posted in #931 (seven acceptance criteria, dry_run dependency, relation to #1157, N2 reconciled with multi-battery phase 2). "
    "Issue #1 reply released the shadow run to LesIT1 after the third review round (main caf9ee4, 340 tests, e2e green).",
)
note(
    "FLEXD-1",
    "Shadow run released to LesIT1 in issue #1 on 2026-10-17 after the Codex review fixes (87bb88f..caf9ee4). Review list fully closed.",
)

# U-1: analysis comment on #1106
note(
    "U-1",
    "Analysis posted on davidusb-geek/emhass#1106 (2026-10-17): per-load priority already exists downstream, the blanket zeroing at optimization.py:7076-7079 is the bug, three-line removal plus two regression cases suggested. Not ours to PR; stays Ideas until someone picks it up.",
)

save_items(data)
print("items.json saved")
