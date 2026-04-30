#!/usr/bin/env python3
"""
PR #831 bookkeeping (AG-7 landing on upstream review):
- Move AG-7 draft card: Status Candidates → Done / Wont Do, body appends PR link.
  Done / Wont Do (not Review) per the corrected workflow — the link card is the
  sole representation in the Review column.
- Add PR-831 as link card to project, Status: Review.
- Sync items.json (Status + body for AG-7; insert PR-831 entry).

Idempotent? No — runs once. Re-running would re-insert the PR-831 link card.
"""

import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ITEMS_FILE = Path(__file__).parent / "items.json"
PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

AG_7_DRAFT_ID = "DI_lAHOAfZrVs4BV1jUzgKbxAY"
AG_7_ITEM_ID = "PVTI_lAHOAfZrVs4BV1jUzgrP8ac"
PR_831_NODE_ID = "PR_kwDOGC8VbM7W6A7Z"

NEW_BODY_SUFFIX = (
    "\n\n**PR:** https://github.com/davidusb-geek/emhass/pull/831 "
    "(opened 2026-04-30, ready for review). Conceptual work item complete; "
    "live PR state is now the authoritative tracker."
)

PR_831_FIELDS = {
    "Status": "Review",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 1.5",
    "Priority": "P1",
    "Effort": "M",
    "Scope": "Upstream",
}


def gh(args, stdin=None):
    r = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, encoding="utf-8", input=stdin
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {r.stderr}")
    return r.stdout


def update_draft_body(draft_id: str, body: str) -> None:
    q = f"""mutation($body: String!) {{
      updateProjectV2DraftIssue(input: {{
        draftIssueId: "{draft_id}"
        body: $body
      }}) {{ draftIssue {{ id title }} }}
    }}"""
    out = gh(["api", "graphql", "-f", f"query={q}", "-f", f"body={body}"])
    title = json.loads(out)["data"]["updateProjectV2DraftIssue"]["draftIssue"]["title"]
    print(f"  body updated: {title}")


def set_field(item_id: str, field_id: str, option_id: str) -> None:
    q = f"""mutation {{
      updateProjectV2ItemFieldValue(input: {{
        projectId: "{PROJECT_ID}"
        itemId: "{item_id}"
        fieldId: "{field_id}"
        value: {{ singleSelectOptionId: "{option_id}" }}
      }}) {{ projectV2Item {{ id }} }}
    }}"""
    gh(["api", "graphql", "-f", f"query={q}"])


def add_content_to_project(content_node_id: str) -> str:
    q = f"""mutation {{
      addProjectV2ItemById(input: {{
        projectId: "{PROJECT_ID}"
        contentId: "{content_node_id}"
      }}) {{ item {{ id }} }}
    }}"""
    out = gh(["api", "graphql", "-f", f"query={q}"])
    return json.loads(out)["data"]["addProjectV2ItemById"]["item"]["id"]


with ITEMS_FILE.open(encoding="utf-8") as f:
    data = json.load(f)
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

# 1. Update AG-7 card on live board
ag_7 = next(it for it in data["items"] if it["id"] == "AG-7")
new_body = ag_7["body"].rstrip() + NEW_BODY_SUFFIX

print("=== Updating AG-7 card ===")
update_draft_body(AG_7_DRAFT_ID, new_body)
set_field(AG_7_ITEM_ID, field_ids["Status"], option_ids["Status"]["Done / Wont Do"])
print("  Status: Candidates → Done / Wont Do")

# 2. Add PR-831 to project
print("\n=== Adding PR-831 link card ===")
pr_831_item_id = add_content_to_project(PR_831_NODE_ID)
print(f"  added item {pr_831_item_id}")
for fname, fval in PR_831_FIELDS.items():
    set_field(pr_831_item_id, field_ids[fname], option_ids[fname][fval])
print(f"  fields set: {PR_831_FIELDS}")

# 3. Sync items.json
print("\n=== Syncing items.json ===")
ag_7["Status"] = "Done / Wont Do"
ag_7["body"] = new_body
print("  AG-7 Status → Done / Wont Do, body updated")

ag_7_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AG-7")
pr_831_entry = {
    "id": "PR-831",
    "title": "PR #831: AGENTS.md (vendor-neutral agent rules) (AG-7)",
    "type": "link",
    "content_id": PR_831_NODE_ID,
    **PR_831_FIELDS,
}
data["items"].insert(ag_7_idx + 1, pr_831_entry)
print("  inserted PR-831 link entry")

with ITEMS_FILE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"  items.json: {len(data['items'])} items total")

print("\n=== Done ===")
