"""Board bookkeeping: PRs #913, #914, #915 merged upstream 2026-06-01.

- #913 (fix #899 single-constant pin outside horizon) — no prior board card existed;
  add PR-913 link card as Done for parity with PR-914/915.
- #914 (AC-4 /healthz) — AC-4 draft -> Done; PR-914 sibling already Done (Project automation, drift-confirmed).
- #915 (AC-2b runtime_params.json) — AC-2b draft -> Done; PR-915 sibling already Done.

Note: AC-2b merge unblocks AC-2c / AM-1b / AM-7 (Candidates) — that re-prioritisation is a
separate planning move, NOT done here.
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DONE = "Done / Wont Do"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]


def to_done(item_id):
    set_field(PROJECT_ID, item_id, field_ids["Status"], option_ids["Status"][DONE])


# 1. AC-2b draft -> Done
ac2b = find_item(data, "AC-2b")
to_done(ac2b["item_id"])
ac2b["Status"] = DONE
print("AC-2b -> Done")

# 2. AC-4 draft -> Done
ac4 = find_item(data, "AC-4")
to_done(ac4["item_id"])
ac4["Status"] = DONE
print("AC-4 -> Done")

# 3. PR-913 link card -> Done (idempotent add; no prior card / no #899 issue card)
PR913_NODE = "PR_kwDOGC8VbM7gmeq3"
PR913_URL = "https://github.com/davidusb-geek/emhass/pull/913"
PR913_TITLE = "fix: skip single-constant pin when window is outside horizon (#899, follows #873/#910)"
PR913_FIELDS = {"Status": DONE, "Category": "A: Code-Lifecycle"}
try:
    find_item(data, "PR-913")
    print("PR-913 already present, skip add")
except KeyError:
    item_id = add_content_to_project(PROJECT_ID, PR913_NODE)
    for k, v in PR913_FIELDS.items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    data["items"].append(
        {
            "id": "PR-913",
            "title": PR913_TITLE,
            "type": "link",
            "content_id": PR913_NODE,
            "Status": DONE,
            "Category": "A: Code-Lifecycle",
            "Phase": None,
            "Priority": None,
            "Effort": None,
            "Scope": None,
            "item_id": item_id,
            "content_url": PR913_URL,
            "repository": "davidusb-geek/emhass",
            "number": 913,
        }
    )
    print(f"added PR-913 -> {item_id}")

# 4. PR-914 / PR-915 siblings already Done via Project automation (drift confirmed) — assert only
for pid in ("PR-914", "PR-915"):
    print(f"{pid} status: {find_item(data, pid)['Status']}")

save_items(data)
print("bookkeeping done")
