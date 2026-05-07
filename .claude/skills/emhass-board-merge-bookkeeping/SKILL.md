---
name: emhass-board-merge-bookkeeping
description: Use when an upstream emhass PR is merged OR closed-without-merge and the davidusb-geek/projects/2 board needs post-PR card moves. Triggers on phrases like "PR #N merged", "PR #N closed", "PR #N wurde geschlossen, nicht gemerged", "won't-do for PR #N", "bookkeeping for PR", "board update for the merge", "ISSUE-N closed", or any PR-close reference paired with the project board.
---

# EMHASS Board Merge Bookkeeping

Project board lives at `davidusb-geek/projects/2`. Source-of-truth in `board/items.json`. Mutation infrastructure in `board/lib.py` and `board/fetch.py`.

## Self-test (one-shot, at first use after this skill was authored)

**STATUS: DONE — baseline executed 2026-05-06 against PR #831 (AG-7).**

Subagent dispatched per protocol (general-purpose, no skill loaded). Outcome: subagent correctly detected idempotent state (AG-7 + PR-831 already at `Done / Wont Do`), ran `fetch.py` first, confirmed `0 drift`, stopped before mutating, switched auth back to `mschaepers`. No skill gaps surfaced — every preflight + idempotency rule was independently rediscovered by the subagent reading `board/lib.py` + `fetch.py` + `items.json`. Confirms skill content matches what a careful first-time reader converges on; serves as documentation rather than load-bearing instructions.

Edge case observed: when no mutation is needed (idempotent re-run), `fetch.py` still produces a timestamp-only diff in `items.json`. Treat as discard-or-commit-as-hygiene per user preference; not a drift signal.

After STATUS: DONE, this section is audit trail only. Do not re-run.

## Pre-flight (always, in order)

1. **Auth** — `gh auth status`. Must show `OptimalNothing90` active. Switch with `gh auth switch --user OptimalNothing90` if not. Project mutations fail without it.
2. **Fetch** — `cd board && python fetch.py`. Refreshes items.json from live, reports drift. Maintainer edits between sessions are invisible until fetched; mutating stale JSON silently overwrites them.
3. **Commit fetch refresh** if drift was non-trivial (body changes, status moves you didn't make). Separate commit from the bookkeeping itself.

## Case detection (open items.json, search by work-item id)

- **Case A — draft umbrella exists** (e.g. AC-2-fix, AG-7, DOC-cookbook). Draft card tracks the conceptual work; PR is a sibling link card. Examples: PR-830 (drives AC-2-fix), PR-831 (drives AG-7).
- **Case B — link-to-issue only** (e.g. ISSUE-818). The Issue itself is the work tracker; PR adds a sibling link card next to the Issue. Example: PR-829 (closes #818).

If unsure: grep items.json for the issue number or feature acronym. No draft entry → Case B.

## Case A actions on merge

1. Draft card `Status` → `Done / Wont Do`
2. PR link card (added when PR opened, was `Status: Review`) → `Status: Done / Wont Do`
3. If PR link card missing: add via `add_content_to_project`, fields mirrored from draft

## Case B actions on merge

1. Issue link card `Status` → `Done / Wont Do` (issue is auto-closed by the merge anyway)
2. Add PR link card via `add_content_to_project`, `Status: Done / Wont Do`, fields mirrored from Issue card; `Category` defaults to `A: Code-Lifecycle` (PR = code change) unless content suggests `Infra` or `B: End-User-Ops`

## One-shot script template

Save as `board/YYYY-MM-DD-pr-N-merged.py`. Get PR node ID via:

```bash
gh api graphql -f query='{ repository(owner:"davidusb-geek",name:"emhass"){pullRequest(number:N){id url number title}} }'
```

Then:

```python
from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
PR_NODE_ID = "PR_..."
PR_URL = "https://github.com/davidusb-geek/emhass/pull/N"
PR_TITLE = "<actual merged PR title>"
PR_FIELDS = {"Status": "Done / Wont Do", "Category": "A: Code-Lifecycle",
             "Phase": "...", "Priority": "...", "Effort": "...", "Scope": "Upstream"}

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

sibling = find_item(data, "ISSUE-N")  # or draft id for Case A
set_field(PROJECT_ID, sibling["item_id"],
          field_ids["Status"], option_ids["Status"]["Done / Wont Do"])
sibling["Status"] = "Done / Wont Do"

try:
    pr_item_id = find_item(data, "PR-N")["item_id"]   # idempotent re-add guard
except KeyError:
    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    for k, v in PR_FIELDS.items():
        set_field(PROJECT_ID, pr_item_id, field_ids[k], option_ids[k][v])
    idx = next(i for i, it in enumerate(data["items"]) if it["id"] == sibling["id"])
    data["items"].insert(idx + 1, {
        "id": "PR-N", "title": PR_TITLE, "type": "link",
        "content_id": PR_NODE_ID, **PR_FIELDS,
        "item_id": pr_item_id, "content_url": PR_URL,
        "repository": "davidusb-geek/emhass", "number": N,
    })

save_items(data)
```

Reference: `board/2026-05-01-pr-829-merged.py` (Case B), `board/2026-04-30-pr-830-bookkeeping.py` (Case A pattern).

## Post-flight

1. `python fetch.py --dry-run` — must report `0 new, 0 removed, 0 changed`. Anything else means a parallel edit happened during your run; investigate before committing.
2. `git add` script + items.json, commit `chore(board): PR #N merged upstream ...`
3. `gh auth switch --user mschaepers` (default account hygiene)
4. Push only when user explicitly asks. Never push autonomously.

## Closed-without-merge mode

Trigger detection: `gh pr view <N> --repo davidusb-geek/emhass --json state,mergedAt`.

| `state` | `mergedAt` | Mode |
|---|---|---|
| `MERGED` | non-null | Standard merge bookkeeping (sections above) |
| `CLOSED` | `null` | Won't-do mode (this section) |

Won't-do mode: same Status target as merge bookkeeping (`Done / Wont Do` is a single
combined option in the project schema), but the script template marks PR-sibling
addition with a "closed-without-merge" intent and the commit message phrasing differs.

### Won't-do mode actions

1. **Read maintainer rationale** — `gh pr view <N> --repo davidusb-geek/emhass --comments`.
   Last 1-3 owner comments captured for documentation.
2. **Same case detection** — Case A (draft umbrella) or Case B (issue-only) per the
   sections above. Logic identical to merge path.
3. **Same Status target** — both Board-Card and PR-link card → `Status: Done / Wont Do`.
4. **PR-link card body** — when adding the PR-sibling card via `add_content_to_project`,
   the script template (Case B) populates the same fields, but the commit message reads
   `chore(board): PR #N closed without merge` (not `merged upstream`).

### Won't-do script template variant

```python
# Same imports + setup as merge template above
from lib import add_content_to_project, find_item, load_items, save_items, set_field

# Won't-do mode: same Status, different intent recorded in commit message.
PR_FIELDS = {"Status": "Done / Wont Do", "Category": "A: Code-Lifecycle",
             "Phase": "...", "Priority": "...", "Effort": "...", "Scope": "Upstream"}
WONT_DO_REASON = "<one-line summary of maintainer rationale>"  # for commit body

# ... rest identical to merge template ...
```

Commit message:

```
chore(board): PR #N closed without merge — <reason>
```

NOT `chore(board): PR #N merged upstream`.

### When to use

Invoke this mode when the user reports "PR #N wurde geschlossen, nicht gemerged" or when
`emhass-cross-repo-flow` Phase 8 detects `state=CLOSED, mergedAt=null` and the user picks
"Won't Do" from the spec §12.c options. Wait & escalate or Re-do paths do NOT trigger
this skill.

## Common mistakes

| Mistake | Reality |
|---------|---------|
| Skipping `fetch.py` before mutating | Stale items.json → silent overwrite of maintainer edits. Always fetch first. |
| Hardcoding `draft_id` / `item_id` constants | items.json now stores them per entry — read with `find_item(data, "X")["draft_id"]`. |
| Re-running without idempotent guard | Re-adds duplicate link cards. Use `find_item` + `try/except KeyError`. |
| Forgetting auth-switch back | Leaves `OptimalNothing90` active; next push goes to wrong remote. Always switch back to `mschaepers` after. |
| Body edits via local `body` field push | Use `lib.append_to_body_idempotent(draft_id, marker, suffix)` — fetches live body first, only appends if marker missing. |
| Treating "PR-N already in items.json" as failure | Drift report can show `[NEW] PR-N` if upstream user added it. Reconcile picks it up; not an error. |

## Red flags — STOP

- About to call `set_field` without first running `fetch.py` in the same session
- About to write `body=` directly via `update_draft_body` (bypasses idempotent append)
- About to commit a script that hardcodes `DI_*` / `PVTI_*` constants instead of reading from items.json

All three mean: stop, refresh, use lib helpers.
