"""Board bookkeeping: PR #995 merged upstream (2026-07-01).

Case A — draft umbrella AC-6 (GET /api/v1/plan) drives the work; PR-995 is a
sibling link card. On merge: AC-6 draft -> Done / Wont Do, add PR-995 link card
(mirrors AC-6 fields) -> Done / Wont Do.
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_NODE_ID = "PR_kwDOGC8VbM7oKRT1"
PR_URL = "https://github.com/davidusb-geek/emhass/pull/995"
PR_TITLE = "feat(api): add GET /api/v1/plan structured plan output"
PR_FIELDS = {
    "Status": "Done / Wont Do",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

# 1) AC-6 draft umbrella -> Done / Wont Do
sibling = find_item(data, "AC-6")
set_field(
    PROJECT_ID,
    sibling["item_id"],
    field_ids["Status"],
    option_ids["Status"]["Done / Wont Do"],
)
sibling["Status"] = "Done / Wont Do"

# 2) Add PR-995 link card (idempotent re-add guard) -> Done / Wont Do
try:
    find_item(data, "PR-995")["item_id"]
except KeyError:
    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    for k, v in PR_FIELDS.items():
        set_field(PROJECT_ID, pr_item_id, field_ids[k], option_ids[k][v])
    idx = next(i for i, it in enumerate(data["items"]) if it["id"] == sibling["id"])
    data["items"].insert(
        idx + 1,
        {
            "id": "PR-995",
            "title": PR_TITLE,
            "type": "link",
            "content_id": PR_NODE_ID,
            **PR_FIELDS,
            "item_id": pr_item_id,
            "content_url": PR_URL,
            "repository": "davidusb-geek/emhass",
            "number": 995,
        },
    )

save_items(data)
print("AC-6 -> Done / Wont Do; PR-995 link card added -> Done / Wont Do")
