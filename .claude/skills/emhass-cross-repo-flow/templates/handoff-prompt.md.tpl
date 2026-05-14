## Handoff-Prompt

**Copy-paste into a NEW Claude Code session opened in `C:/Users/MauricioSchäpers/claude-code/emhass/` (the fork):**

````
You are a fork-session for emhass upstream PR work. The main planning session lives in
`C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`. You operate ONLY here in
the `emhass` fork repo.

## AGENTS.md is your rulebook

Before Task 1, read `AGENTS.md` in the fork repo root (`cat AGENTS.md`). It is the
single source of truth for AI-coder rules on this codebase. Follow:

- **§3 Don't-touch invariants** — mandatory, do not violate without main-session sign-off.
- **§4 Maintainer scope corridors** — cite the source if a contributor questions scope.
- **§5 Limits and gotchas** — file-issue-not-PR rules, verify-before-done checklist,
  no-refactor-without-issue, "Adding a parameter" / "Changing a default value" workflows,
  forecast-feed-alignment rule, common AI hallucinations to avoid.
- **§6 Behavioral guardrails** (if present on master): Think first / Simplicity /
  Surgical / Goal-driven. Karpathy four-rule framework. Added by PR #848 — if not on
  current master, apply the four rules anyway from inline note below.
- **§7 Conventions** — commit-prefix style (`fix`/`docs`/`feat`/`chore`), Diátaxis doc style.

Item-specific scope under "Out of scope (this session)" below SUPERSEDES AGENTS.md
ONLY where named explicitly. Otherwise AGENTS.md wins.

Inline fallback if §6 not yet on master:
1. **Think first.** State assumptions; ask if uncertain; surface tradeoffs; push back on overcomplication.
2. **Simplicity.** Minimum code that solves the stated problem; no speculative features or abstractions.
3. **Surgical.** Touch only what the plan/spec names; match existing style; remove only orphans YOUR change created.
4. **Goal-driven.** Verifiable success criteria; loop until verified; do not declare done before validation passes.

## Item context
- Board ID: {{board_id}}
- Issue: {{issue_link_or_none}}
- Goal-fit: {{goal_fit}}
- Spec: `{{spec_relative_path}}`
- Plan: `{{plan_relative_path}}`

The spec and plan are in the sibling repo. Read them via:
  cat ../emhass-contributions/{{spec_relative_path}}
  cat ../emhass-contributions/{{plan_relative_path}}

## Pre-flight (mandatory, in order)
1. `gh auth status` — must show `OptimalNothing90` active. Switch with
   `gh auth switch --user OptimalNothing90` if not.
2. `git fetch upstream && git checkout upstream/master`
3. `git checkout -b {{branch_name}}` (exact name, do not invent)
4. Verify clean tree before edits: `git status` should show empty.

## Implementation
Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development` if the
plan recommends it). Plan path: `../emhass-contributions/{{plan_relative_path}}`.
Follow the plan step-by-step. Do NOT improvise scope.

## PR creation — DRAFT FIRST

Open the PR as a **draft** so CI, CodeQL, and sourcery-AI run before the maintainer sees
it. Convention: every PR opens as draft unless the item is a true 1-3 line edit
(direct-path XS).

After all plan tasks complete and local tests pass:

  git push -u origin {{branch_name}}
  gh pr create \
    --draft \
    --repo davidusb-geek/emhass \
    --base master \
    --head OptimalNothing90:{{branch_name}} \
    --title "{{pr_title}}" \
    --body-file - <<'EOF'
{{pr_body_skeleton}}
EOF

Then capture the PR URL and number, and proceed to the Mark-ready section below.

## Mark-ready (after CI + alerts triaged)

Once the draft PR is open, watch CI on the PR URL. Do **not** call
`gh pr ready` (which un-drafts the PR) until ALL of:

- Every CI check on the PR is green (build matrix, tests, lint). Use
  `gh pr checks {{pr_number_or_url}} --watch` if you want to block here.
- CodeQL produced **0 alerts** OR every alert is either:
  - fixed in a follow-up commit on the same branch, OR
  - explicitly triaged with a comment-reply on the alert explaining false-positive
    rationale (do NOT dismiss alerts unilaterally — main session co-signs dismissal).
- Sourcery-AI review comments either applied in a follow-up commit, OR explicitly
  replied "won't-fix because X" with reasoning.
- A self-review walk of the PR diff is done (read every changed line, confirm nothing
  beyond the spec leaked in).
- All "Out of scope (this session)" items below are truly absent from the diff.

When all five gates pass:

  gh pr ready {{pr_number_or_url}}

Emit HANDOFF-RESULT only AFTER `gh pr ready` succeeds. The `status: pr-open` value
means "ready for maintainer review", not "draft sitting on CI".

If CI fails or alerts cannot be resolved within this session, emit HANDOFF-RESULT with
`status: blocked` and the draft PR URL in the `notes` field. Main session will pivot.

## Return contract — required output back to main session
Send the user a single message in this format so they can paste it into the
main planning session:

```
HANDOFF-RESULT {{board_id}}
status: pr-open | blocked | failed
pr-url: <url-or-none>
branch: {{branch_name}}
tests: pass | fail | skipped
notes: <one-line summary OR pivot reason if blocked>
```

## Pivot trigger (if plan is wrong)
If during implementation you discover the plan does not match upstream code reality
(file moved, function renamed, assumption broken):
1. Do NOT improvise a new plan.
2. Do NOT push partial work.
3. Stop, write a `## Pivot Reason` section appended to
   `../emhass-contributions/{{plan_relative_path}}` with concrete divergence facts
   (file:line citations).
4. Set Return-status to `blocked`. Main session re-plans.

## Out of scope (this session)
- Spec edits — those happen in main session
- Board mutations — those happen in main session via `emhass-board-merge-bookkeeping`
- Account switching back — main session handles after merge

## Session resumability — DO NOT close after HANDOFF-RESULT
This fork-session may be needed again. After you emit the HANDOFF-RESULT block:
- Keep this Claude Code session OPEN (do not type `/exit`, do not close the terminal).
- Main session will instruct you to resume via `claude --resume` from
  `C:/Users/MauricioSchäpers/claude-code/emhass/` if pivots, code-review feedback,
  or follow-up edits arrive.
- This preserves your walked git-tree state, grep results, and decision history —
  far cheaper than starting fresh.
- If you must close (e.g. machine restart), note: future-you will `claude --resume`
  in the fork directory and pick this session from the menu (most-recent one for the
  board id above is the right pick).
````

After Fork-Session reports HANDOFF-RESULT, return to the main planning session and paste
the result block. Main session will:
- On `pr-open`: update Board-Card to `Status: Review`
- On `blocked`: read appended Pivot Reason, re-plan — re-routing instructions will tell
  the user to resume the SAME fork session (`claude --resume` in fork dir, pick latest),
  not open a new one
- On `failed`: triage, decide
