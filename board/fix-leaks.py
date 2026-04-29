#!/usr/bin/env python3
"""
Remove references to private repo / personal account from public-bound board items:
- AG-7 (AGENTS.md goes upstream)
- AG-pr-readiness (will become a plugin)
- AG-B1 (placeholder repo name)
- AC-2a (account-switch hygiene is personal, not board content)
- AC-2-fix (same)
"""
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "2026-04-28-emhass-board-migration-items.json"


def fetch_draft_ids():
    q = '''
    { node(id: "PVT_kwHOAfZrVs4BV1jU") {
      ... on ProjectV2 { items(first: 100) {
        nodes {
          content { ... on DraftIssue { id title } }
        }
      } } } }
    '''
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"],
                       capture_output=True, text=True, encoding="utf-8")
    out = json.loads(r.stdout)
    ids = {}
    for n in out["data"]["node"]["items"]["nodes"]:
        c = n.get("content")
        if c and c.get("title"):
            for tid in ("AG-7", "AG-pr-readiness", "AG-B1", "AC-2a", "AC-2-fix"):
                if c["title"].startswith(tid + ":") or c["title"].startswith(tid + " "):
                    ids[tid] = c["id"]
    return ids


def update_draft(draft_id, body):
    q = f'''mutation($body: String!) {{
      updateProjectV2DraftIssue(input: {{
        draftIssueId: "{draft_id}"
        body: $body
      }}) {{ draftIssue {{ title }} }}
    }}'''
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}", "-f", f"body={body}"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"gh failed: {r.stderr}")
    title = json.loads(r.stdout)["data"]["updateProjectV2DraftIssue"]["draftIssue"]["title"]
    print(f"  updated {title}")


with DATA_FILE.open(encoding="utf-8") as f:
    data = json.load(f)
existing = {it["id"]: it for it in data["items"]}

# Compose new bodies via targeted replacements
fixes = []

# AG-7: drop the loxonesmarthome bullet (already done in prior run, idempotent)
ag7 = existing["AG-7"]["body"]
ag7_new = ag7.replace(
    "- `docs/superpowers/specs/` (in OptimalNothing90/loxonesmarthome) — design specs that fed concrete PRs (visible audit trail)\n",
    ""
)
if ag7_new != ag7:
    fixes.append(("AG-7", ag7_new))

# AG-pr-readiness (already done in prior run, idempotent re-application)
agpr = existing["AG-pr-readiness"]["body"]
agpr_new = agpr.replace(
    "Lives at: `.claude/skills/emhass-pr-readiness/SKILL.md` (loxonesmarthome local).",
    "Lives at: `.claude/skills/emhass-pr-readiness/SKILL.md` in your local Claude Code skills directory."
).replace(
    'Account check: `gh auth status | grep "Active.*OptimalNothing90"` before push',
    'Account check: `gh auth status` shows the right account active before push (relevant for contributors juggling personal + org accounts)'
)
if agpr_new != agpr:
    fixes.append(("AG-pr-readiness", agpr_new))

# AG-B1: replace OptimalNothing90/<plugin-repo> placeholder with generic
agb1 = existing["AG-B1"]["body"]
agb1_new = agb1.replace(
    "Likely name: `OptimalNothing90/claude-code-emhass-plugin` or community-suggested",
    "Repo name TBD — community-suggested or maintainer-blessed"
).replace(
    "without needing the OptimalNothing90 local Loxone/Tibber/EVCC stack",
    "without needing the original contributor's specific Loxone/Tibber/EVCC stack"
)
if agb1_new != agb1:
    fixes.append(("AG-B1", agb1_new))

# AC-2a: drop account-hygiene line (personal, not board content)
ac2a = existing["AC-2a"]["body"]
ac2a_new = ac2a.replace(
    "Account: switch to OptimalNothing90 before push, switch back to mschaepers afterward.\n\n",
    ""
).replace(
    "Account: switch to OptimalNothing90 before push, switch back to mschaepers afterward.",
    ""
)
if ac2a_new != ac2a:
    fixes.append(("AC-2a", ac2a_new))

# AC-2-fix: same
ac2fix = existing["AC-2-fix"]["body"]
ac2fix_new = ac2fix.replace(
    "Account: switch to OptimalNothing90 before push.\n",
    ""
).replace(
    "Account: switch to OptimalNothing90 before push.",
    ""
)
if ac2fix_new != ac2fix:
    fixes.append(("AC-2-fix", ac2fix_new))

if not fixes:
    print("No fixes needed.")
    sys.exit(0)

print("=== Fetching draft IDs ===")
draft_ids = fetch_draft_ids()
for tid, _ in fixes:
    if tid not in draft_ids:
        raise RuntimeError(f"draft id missing for {tid}")

print("\n=== Applying ===")
for tid, new_body in fixes:
    print(f"{tid}:")
    update_draft(draft_ids[tid], new_body)
    existing[tid]["body"] = new_body

with DATA_FILE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"\n  items.json synced ({len(fixes)} bodies updated)")
