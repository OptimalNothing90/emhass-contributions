#!/usr/bin/env python3
"""
PR #830 bookkeeping (AC-2-fix landing on upstream review):
- Update AC-2-fix card: Status Ideas → Review, body appends PR link
- Add PR-830 as link card to project
- Sync items.json (Status + body for AC-2-fix; insert PR-830 entry)

Idempotent? No — runs once. Do not re-run after success without commenting
out the create section (PR-830 link would be added a second time).
"""

import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ITEMS_FILE = Path(__file__).parent / "items.json"
PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

AC_2_FIX_DRAFT_ID = "DI_lAHOAfZrVs4BV1jUzgKbxqk"
AC_2_FIX_ITEM_ID = "PVTI_lAHOAfZrVs4BV1jUzgrQM78"
PR_830_NODE_ID = "PR_kwDOGC8VbM7W5jdY"

NEW_BODY_SUFFIX = (
    "\n\n**PR:** https://github.com/davidusb-geek/emhass/pull/830 "
    "(opened 2026-04-30, awaiting maintainer review)"
)

PR_830_FIELDS = {
    "Status": "Review",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 1",
    "Priority": "P2",
    "Effort": "XS",
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

# 1. Update AC-2-fix card on live board
ac_2_fix = next(it for it in data["items"] if it["id"] == "AC-2-fix")
new_body = ac_2_fix["body"].rstrip() + NEW_BODY_SUFFIX

print("=== Updating AC-2-fix card ===")
update_draft_body(AC_2_FIX_DRAFT_ID, new_body)
set_field(AC_2_FIX_ITEM_ID, field_ids["Status"], option_ids["Status"]["Review"])
print("  Status: Ideas → Review")

# 2. Add PR-830 to project
print("\n=== Adding PR-830 link card ===")
pr_830_item_id = add_content_to_project(PR_830_NODE_ID)
print(f"  added item {pr_830_item_id}")
for fname, fval in PR_830_FIELDS.items():
    set_field(pr_830_item_id, field_ids[fname], option_ids[fname][fval])
print(f"  fields set: {PR_830_FIELDS}")

# 3. Sync items.json
print("\n=== Syncing items.json ===")
ac_2_fix["Status"] = "Review"
ac_2_fix["body"] = new_body
print("  AC-2-fix Status → Review, body updated")

ac_2_fix_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AC-2-fix")
pr_830_entry = {
    "id": "PR-830",
    "title": "PR #830: param_definitions.json default mismatches (AC-2-fix)",
    "type": "link",
    "content_id": PR_830_NODE_ID,
    **PR_830_FIELDS,
}
data["items"].insert(ac_2_fix_idx + 1, pr_830_entry)
print("  inserted PR-830 link entry")

with ITEMS_FILE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"  items.json: {len(data['items'])} items total")

print("\n=== Done ===")
