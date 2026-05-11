---
name: emhass-cross-repo-flow
description: Use when starting work on a Type-1 (upstream PR) emhass board item. Triggers on phrases like "lass uns AC-2a angehen", "let's do AG-7", "starten wir ag-b1", "issue #826 angehen", "PR für 824 vorbereiten", "auf goodwill #343 fixen", or generic "ich will PR machen für …" / "lass uns das nächste angehen" when item context is clear from prior turn. Orchestrates routing assessment → spec → plan → handoff-prompt → board status updates and chains into `emhass-board-merge-bookkeeping` on PR close (merged or not). Does NOT fire on Type-2 audits/RFCs, "what's next?" without item (that's the picker), or "write the bookkeeping script" (that's the bookkeeping skill).
---

# EMHASS Cross-Repo Flow

Orchestrates the multi-repo contribution loop:

```
items.json → routing → spec → plan → handoff-prompt → fork session → PR → bookkeeping → next item?
```

Scope: Type-1 items (`Scope=Upstream`). Type-2 (audit/RFC) and Type-3 (Local) items are
explicitly out of scope per spec Decision #6.

## Self-test (one-shot, at first use after this skill was authored)

**STATUS: DONE — baseline executed 2026-05-07 against AC-2a (board id `AC-2a`).**

Outcome: routing-assessment correctly recommended `plan-light` (audit + no bug + no
maintainer engagement). Spec + plan written at expected paths; handoff-prompt section
appended with all placeholders resolved including `branch_name=feat/ac-2a-unit-field`
(deterministic per `feedback_branch_naming`). Board card moved Candidates → In Progress and
back to Candidates for cleanup (deviation: live AC-2a was Status=Candidates/Phase 3, not
Todo/Phase 1 as expected — board state had evolved since spec was written; mutation
mechanism validated equivalently). Self-test stopped before fork session as designed; no
upstream PR opened. Spec + plan retained as `_self-test artefact_` — kept as audit
trail.

After STATUS: DONE, this section is audit trail only.

First live use after authoring runs the skill against AC-2a (board id `AC-2a`) per spec §13.2 / §13.3:

1. Routing-Assessment fires; item snapshot lists Phase 1, P1, Effort S, audit `audits/2026-04-28-param-definitions.md`, issue #826 open with no maintainer engagement.
2. Recommended path = `plan-light` (audit exists → reasoning documented).
3. Skill writes spec to `docs/superpowers/specs/2026-05-08-ac-2a-design.md` via `templates/spec.md.tpl`.
4. Skill invokes `superpowers:writing-plans` to produce `docs/superpowers/plans/2026-05-08-ac-2a.md`.
5. Skill appends `## Handoff-Prompt` section to the plan via `templates/handoff-prompt.md.tpl`.
6. Skill moves AC-2a board card `Status: Todo → In Progress`.
7. Skill prints handoff prompt to user but **stops before fork-session opens**. Branch is NOT created in the fork; PR is NOT opened.
8. After verification, the user reverts the board card to `Status: Todo` and (optionally) deletes the spec/plan files. Flip this STATUS marker to `DONE` with a one-line note documenting outcome (paths produced, any deviations).

Pass criteria:
- Spec exists at expected path
- Plan exists at expected path with `## Handoff-Prompt` section
- Handoff prompt contains the resolved `branch_name = feat/ac-2a-unit-field` (per `feedback_branch_naming`)
- Board card was moved to `In Progress` (visible in `items.json` after `fetch.py`)
- No fork-side commits, no upstream PR

After STATUS: DONE, this section is audit trail only.

## Pre-flight (always, in order)

1. **Auth** — `gh auth status`. Must show `OptimalNothing90` active. Switch with
   `gh auth switch --user OptimalNothing90` if not. Required for board mutations and
   issue lookups.
2. **Working directory** — `git rev-parse --show-toplevel` must equal the
   `emhass-contributions` repo path. This skill must NOT run in the fork repo.
3. **Tree state** — `git status` should be clean OR have only docs/superpowers edits in
   flight. Halt and ask if tree is dirty with non-docs changes.
4. **items.json freshness** — `cd board && python fetch.py --dry-run`. If drift, run
   `python fetch.py` and commit. Stale state misroutes (e.g. shows item as Todo when it's
   already In Progress upstream).
5. **Resume detection** — search `docs/superpowers/{specs,plans}/*.md` for files matching
   the board id. If found:
   - spec only, no plan → resume at writing-plans
   - spec + plan → check whether the plan has a `## Pivot Reason` section
     - if yes → re-plan path (see §Pivot)
     - if no → ask user: regenerate handoff or abort? (don't double-issue handoffs)

## Phase 1 — Routing-Mini-Assessment

Read item context (in order):

1. Board item from `board/items.json` (use `find_item` from `board/lib.py`).
2. Linked issue, if any: `gh issue view <N> --repo davidusb-geek/emhass --json title,body,labels,comments,author`.
3. Existing audit/RFC if body references one (`audits/...md`, `rfcs/...md`).
4. Existing spec/plan with same board id (already done in pre-flight Step 5).

Apply signal table (per spec §11):

| Signal | Implication |
|---|---|
| Bug-label on linked issue | **HARD-STOP.** Per `feedback_no_auto_bugfix`: ask "goodwill or eigen-betroffen?" before continuing. (a)/(b)/(c). User answer unlocks the rest of routing. |
| Existing audit/RFC | `plan-light` — reasoning already documented |
| Maintainer commented in last 14d with solution direction | `plan-light` — well-defined task |
| Maintainer linked PR as solution to issue | **HARD-STOP.** Item is in flight upstream; ask user before parallel-work |
| Goal-fit = EV-EVCC or LLM-ready, no audit/RFC | `brainstorm` — strategic, **PR-first** per `feedback_pr_first_for_strategic`. Goal streams defined in `project_strategic_goals`. Skip RFC-first path. |
| Goal-fit = empty, no audit/RFC | `brainstorm` with "really worth doing?" check |
| Effort = XS, 1-3-line edit / doc typo | `direct` — handoff only, no spec/plan |

Present the routing-assessment to the user in the format from spec §11 ("sample output"
section). Always present the recommended path AND the alternatives (`brainstorm` /
`plan-light` / `direct` / `abbrechen`).

User-response handling:
- `"plan-light"` / `"go"` / `"empfohlen"` → proceed with recommended path
- `"brainstorm"` → invoke `superpowers:brainstorming` with pre-loaded context
- `"direct"` → handoff-prompt only, no spec/plan
- `"abbrechen"` / `"stop"` → exit; no board update
- A content question → answer, then re-ask the routing question

### Bug-label special case

Print the §11 "Bug special-case" template verbatim. User answers (a)/(b)/(c) before
routing continues. (a) and (b) unlock; (c) requires explicit reason.

### Strategic-item special case (PR-first)

Print the §11 "Strategic-item special-case" template verbatim. RFC-first only acceptable
if maintainer engaged on issue/discussion or open corridor-block exists.

## Phase 2 — Spec production

Path = `plan-light`:
- Read `templates/spec.md.tpl`, fill placeholders from item / issue / audit
- Write to `docs/superpowers/specs/{YYYY-MM-DD}-{board_id_lowercase}-design.md`
- The board id slugifies as: lowercase, replace spaces with `-` (e.g. `AC-2a` stays
  `ac-2a`; `EV-1` stays `ev-1`)

Path = `brainstorm`:
- Invoke `superpowers:brainstorming` skill with item context. Brainstorming writes the
  spec to `docs/superpowers/specs/...`. This skill does not reimplement.

Path = `direct`:
- No spec. Skip to Phase 4 (handoff only).

After spec exists, confirm path with user before invoking writing-plans.

## Phase 3 — Plan production

Invoke `superpowers:writing-plans` with the spec path. Writing-plans produces the plan
body in AG-7 style (Goal, Architecture, Tech Stack, File Structure, Tasks).

After plan body is written, append `## Handoff-Prompt` section by reading
`templates/handoff-prompt.md.tpl` and filling placeholders (see Phase 4).

Plan filename: `docs/superpowers/plans/{YYYY-MM-DD}-{board_id_lowercase}.md`.

## Phase 4 — Handoff-prompt assembly

Resolve branch name deterministically per `feedback_branch_naming`:

| Source | Pattern | Example |
|---|---|---|
| Board item with strategic feature | `feat/<board-id-lower>-<short-slug>` | `feat/ac-2a-unit-field` |
| Issue-driven bug fix | `fix/i<issue>-<short-slug>` | `fix/i343-batt-efficiency` |
| Documentation | `docs/<board-id-lower>` | `docs/ag-7` |
| Tooling / hygiene | `chore/<board-id-lower>` | `chore/board-tooling` |

The skill MUST resolve and emit the exact branch name in the handoff prompt. Never
"pick a good branch name yourself" — that drift violates `feedback_branch_naming`.

Fill `templates/handoff-prompt.md.tpl` placeholders:

| Placeholder | Source |
|---|---|
| `{{board_id}}` | item id from picker / user-named |
| `{{issue_link_or_none}}` | from item `content_url` if `type=link`; else `None` |
| `{{goal_fit}}` | `goal_fit(item)` from `board/next.py` (or repeat the rule inline) |
| `{{spec_relative_path}}` | computed in Phase 2 |
| `{{plan_relative_path}}` | computed in Phase 3 |
| `{{branch_name}}` | resolved per the table above |
| `{{pr_title}}` | from spec §1 / issue title; conventional commit prefix per branch type |
| `{{pr_body_skeleton}}` | spec sections 1+2+9 + issue link, no LLM padding |

Append the rendered template to the plan file as a new `## Handoff-Prompt` section.

## Phase 5 — Board card status update

After plan + handoff-prompt are written:

1. `cd board && python fetch.py` (refresh first — same hygiene as bookkeeping skill)
2. Author a one-shot script `board/{YYYY-MM-DD}-{board_id_lowercase}-start.py` that:
   - Imports `find_item, set_field` from `board/lib.py`
   - Sets `Status: Todo → In Progress` for the board card
   - Saves items.json
3. Run the script
4. `python fetch.py --dry-run` → must show 0 drift
5. Commit: `chore(board): start {board-id} ({YYYY-MM-DD})`

Reference structure (from `emhass-board-merge-bookkeeping` skill, adapted for status-only
mutation):

```python
from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
set_field(PROJECT_ID, item["item_id"],
          field_ids["Status"], option_ids["Status"]["In Progress"])
item["Status"] = "In Progress"
save_items(data)
```

## Phase 6 — Hand off to fork session

Output the rendered handoff prompt block **directly in the chat message** (not only as a
file-path reference — user preference 2026-05-11: handoff prompts always emitted inline so
copy-paste is one click). Use the fenced code block from `templates/handoff-prompt.md.tpl`
with all placeholders resolved.

Tell the user:

> "Open a NEW Claude Code session in `C:/Users/MauricioSchäpers/claude-code/emhass/`,
> paste the prompt above. **Keep that session open** after it reports back — re-routes
> and follow-ups resume the same session via `claude --resume`, never a fresh one. Come
> back here with the `HANDOFF-RESULT` block when fork-session reports."

The handoff-prompt template carries a `## Session resumability` section at the bottom
that instructs the fork-session not to close after HANDOFF-RESULT. This skill's Phase 7
+ Pivot pathways assume the fork session is resumable.

Skill exits this phase. State is persisted in items.json + plan file. User decides
when to re-engage.

## Phase 7 — Receive HANDOFF-RESULT

When the user pastes back a `HANDOFF-RESULT <board_id>` block, parse the four fields:
`status`, `pr-url`, `branch`, `tests`, `notes`.

| status | Action |
|---|---|
| `pr-open` | Add PR sibling card via bookkeeping helpers (see spec §10's "On pr-open" path); set Board-Card to `Status: Review`; await maintainer |
| `blocked` | Read `## Pivot Reason` section from the plan file (fork-session appended it). Move to Pivot pathway (a) below |
| `failed` | Triage with user; do not auto-rollback. Could be auth issue, missing branch, gh CLI bug |

For `pr-open`: write a short script analogous to Phase-5's start script, but adding the
PR sibling card and moving Board-Card to `Review`. Use `add_content_to_project` from
`board/lib.py` (idempotent guard via `find_item`).

## Phase 8 — On PR close (chain into bookkeeping)

When the user reports the PR closed (merged or otherwise), invoke
`emhass-board-merge-bookkeeping` skill. That skill handles:
- Merge → standard bookkeeping (Case A or B)
- Closed-not-merged → won't-do mode (added by Task 16 of this plan)

Cross-repo-flow exits after delegating.

## Phase 9 — Loop-end prompt (halbautomatisch)

After bookkeeping completes (user confirms `STATUS: DONE`), ask:

> "Pick next item? (j/n)"

- `j` / `ja` / `yes` → invoke `emhass-next-item-picker`
- `n` / `nein` / `no` → exit, log nothing
- Anything else → ask once more, then default to `n`

This is the only auto-chain in the skill. Per spec Decision #7, never proceed without
explicit confirmation.

## Pivot pathways

### (a) Plan is wrong (fork-session-discovered)

Trigger: user pastes `HANDOFF-RESULT <id>` with `status: blocked`.

Actions:
1. `gh auth status` — confirm OptimalNothing90
2. Read the plan's `## Pivot Reason` section
3. Move Board-Card back to `Status: Todo` (no `Blocked` status exists in the project)
4. Present three options to user:
   - **Re-plan in place** — invoke `superpowers:writing-plans` again with updated context.
     Mark the old plan with `[SUPERSEDED-BY: <new-plan-path>]` at top; do not delete.
   - **Spec revision** — if divergence touches design assumptions, re-enter
     `superpowers:brainstorming` for that decision only. Append `## Revisions` to spec.
   - **Drop item** — upstream reality makes work irrelevant. Mark Won't Do via
     `emhass-board-merge-bookkeeping` (won't-do mode), document, exit.
5. User chooses → corresponding path

What does NOT happen:
- No auto-re-plan without explicit user confirmation
- No fork-side branch deletion (user manages)
- No bookkeeping invocation unless user picks "Drop item"

When re-routing the fork-session for re-plan or re-spec, the instructions to the user
ALWAYS read:

> "Resume the fork session: `cd C:/Users/MauricioSchäpers/claude-code/emhass && claude --resume`,
> pick the `<board-id>` session from the menu, then paste the following: [...new prompt...]"

**Never** "open a new fork session" — that loses the walked context. The handoff-prompt
template instructed the fork-session to stay resumable; honor that.

### (c) PR closed-not-merged

Trigger: `gh pr view <N> --repo davidusb-geek/emhass --json state,mergedAt` shows
`state=CLOSED, mergedAt=null`. User can also surface manually: "PR #N wurde geschlossen,
nicht gemerged".

Actions:
1. `gh auth status` — confirm OptimalNothing90
2. Read maintainer comments: `gh pr view <N> --repo davidusb-geek/emhass --comments`.
   Surface the most recent owner comment to user.
3. Present three options (per spec §12.c):
   - **Won't Do** — invoke `emhass-board-merge-bookkeeping` with won't-do mode flag
   - **Re-do with changes** — append `## Revisions` to spec; mark plan SUPERSEDED-BY;
     re-enter routing
   - **Wait & escalate** — exit, board unchanged
4. User chooses → corresponding path

## Out of scope (per spec §15)

- Type-2 (audit/RFC) and Type-3 (Local) item orchestration — handled ad-hoc
- Vollautomatic loop chaining without user confirmation — per Decision #7
- Auto-pickup in fork-session via marker files — explicitly manual copy-paste
- Cross-session FS state synchronization — board is single source of truth (Decision #9)
- PR review iteration helper (Pivot b) — left manual (Decision #8 b)
- Parallel item slot management — user self-discipline (Decision #8 d)
- LLM-generated branch names, PR titles, commit messages — all deterministic
- Schema migration of `items.json` to add `Goal` field — opt-in per item

## Common mistakes

| Mistake | Reality |
|---|---|
| Inventing a branch name in the handoff prompt | Violates `feedback_branch_naming`; resolve deterministically per the table |
| Suggesting "let's open an RFC first" for a strategic item | Violates `feedback_pr_first_for_strategic`; recommend PR-first |
| Surfacing a bug-labelled item without the (a)/(b)/(c) prompt | Violates `feedback_no_auto_bugfix` |
| Skipping `fetch.py` before mutating board card | Stale items.json overwrites maintainer edits |
| Writing the handoff prompt as freeform text | Use `templates/handoff-prompt.md.tpl`; freeform drift loses fields |
| Continuing on `status: blocked` without reading `## Pivot Reason` | Skips evidence; blind re-plan repeats the failure |
| Auto-running picker after bookkeeping without asking | Violates Decision #7 (halbautomatisch) |

## Red flags — STOP

- About to write a branch name not derivable from board-id / issue-number
- About to invoke `superpowers:writing-plans` without a spec on disk
- About to mutate `Status` without running `fetch.py` first
- About to skip the routing-assessment because "the path is obvious"
