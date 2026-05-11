## Handoff-Prompt

**Copy-paste into a NEW Claude Code session opened in `C:/Users/MauricioSchäpers/claude-code/emhass/` (the fork):**

````
You are a fork-session for emhass upstream PR work. The main planning session lives in
`C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`. You operate ONLY here in
the `emhass` fork repo.

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

## PR creation
After all plan tasks complete and tests pass:

  git push -u origin {{branch_name}}
  gh pr create \
    --repo davidusb-geek/emhass \
    --base master \
    --head OptimalNothing90:{{branch_name}} \
    --title "{{pr_title}}" \
    --body-file - <<'EOF'
{{pr_body_skeleton}}
EOF

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
