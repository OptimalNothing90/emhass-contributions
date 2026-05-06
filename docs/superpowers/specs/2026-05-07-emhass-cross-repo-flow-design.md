# `emhass-cross-repo-flow` — Design

**Date:** 2026-05-07
**Topic:** Skill + script suite to orchestrate the contribution loop across `emhass-contributions` ↔ `emhass` fork ↔ `davidusb-geek/emhass` upstream
**Target repo:** `OptimalNothing90/emhass-contributions` (this repo)
**Effort:** M (meta-tooling, no upstream PR)
**Phase / Priority:** N/A (internal infra)
**Goal-fit:** Infra (enables LLM-ready and EV-EVCC delivery streams)

## 1. Problem

Contribution work to `davidusb-geek/emhass` follows a recurring multi-repo loop:

1. Pick next board item from `items.json` (priority-aligned with strategic goals)
2. Decide if brainstorm/spec/plan is needed
3. Write spec + plan in `emhass-contributions`
4. Hand off to a separate Claude Code session in `claude-code/emhass/` (the fork)
5. Fork-session implements, opens PR
6. Maintainer reviews; on merge: board cleanup via existing `emhass-board-merge-bookkeeping` skill
7. Loop back to step 1

Today step 1, 2, 4, and the post-merge → next-item transition are improvised in chat each time. Friction:

- Board state is read manually; no ranked candidate suggestions
- Brainstorm-vs-plan-light decision is ad-hoc, sometimes overshoots (full brainstorm for 5-LOC fix) or undershoots (no spec for strategic items)
- Hand-off prompt to the fork session is hand-typed each time, drifts in completeness, branch names get LLM-generated instead of deterministic
- No standard return contract from fork-session → main-session, status sync is manual
- Pivot pathways (plan turns out wrong, PR closed-not-merged) are recovered case-by-case
- Loop chaining ("what's next?") requires user to re-bootstrap context

## 2. Goal

Encode the loop as two new skills + one Python script, leveraging existing infra:

- `board/next.py` — picker logic over `items.json`; ranked candidate output
- `emhass-next-item-picker` skill — wrapper that presents picker output, hands off to flow
- `emhass-cross-repo-flow` skill — orchestrates spec → plan → handoff → board updates → eventual bookkeeping; chains into existing `emhass-board-merge-bookkeeping` on merge
- Integration with existing `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:executing-plans`, `emhass-board-merge-bookkeeping`

Scope = Type-1 items only (upstream-PR work, `Scope=Upstream` or `Both`). Audits/RFCs/local-only items (Type 2/3) deliberately not orchestrated by this skill — they have different rhythms and don't justify shared abstraction today.

## 3. Decisions (from brainstorming)

| # | Topic | Choice | Why |
|---|-------|--------|-----|
| 1 | Skill form | Single `emhass-cross-repo-flow` skill, chains into existing `emhass-board-merge-bookkeeping` for cleanup | One conceptual entry point; existing post-merge skill stays as-is. No duplication. |
| 2 | Next-item logic | Separate `emhass-next-item-picker` skill + `board/next.py` script | Picker logic is deterministic filter+rank — belongs in script, testable. Skill = thin wrapper for conversational presentation. |
| 3 | Routing decision | Adaptive ask-user mini-assessment | Heuristic gets edge cases wrong; cheaper to ask explicitly than recover from mis-routing. Forces skill to actually read the item context before recommending. |
| 4 | Spec/plan production | Always both spec + plan, mini-form for plan-light path | Consistent structure for picker/bookkeeping lookup. Mini-form = same skeleton, less verbose content. |
| 5 | Picker ranking | Two lists per call: Quick-Win + Strategic | Two needs (momentum vs. impact) — better to surface both than to settle on one heuristic. |
| 6 | Skill scope | Type-1 (upstream PR items) only | YAGNI; existing examples are all Type-1; Type-2/3 retrofittable later if real volume materializes. |
| 7 | Loop chaining | Halbautomatisch — skill ends with prompt "next item?" | Vollautomatisch is intrusive; explicit-only loses self-runner feel. |
| 8 | Failure handling | Minimum-viable pivot: (a) plan-wrong + (c) PR-closed-not-merged covered explicitly. (b) review iterations + (d) parallel items left manual. | (a) and (c) recur; (b)/(d) are rare and low-cost to handle ad-hoc. |
| 9 | Status sync | Board-card sync (single source of truth) | `items.json` is already authoritative; second status store would drift. |
| 10 | PR-first for strategic items | Skip RFC-first path for strategic features without maintainer engagement | Maintainer has no bandwidth for idea review; PRs land more reliably than discussions. |
| 11 | Branch naming | Deterministic `<type>/<board-id-or-issue>-<slug>` | Auditable, grep-able, ties branch identity to board card. Never LLM-generated. |
| 12 | Bug-label items | Default-skip in picker; require explicit user opt-in | Strategic focus is own roadmap, not random upstream triage. |

## 4. Architecture overview

```
┌─ User-Input ────────────────────────────────────────┐
│                                                     │
│  "was kommt als nächstes?"                          │
│       │                                             │
│       ▼                                             │
│  emhass-next-item-picker (NEW, skill)               │
│       │  invokes → board/next.py (NEW, script)      │
│       │            → reads items.json               │
│       │            → filters (Status=Todo, no bug,  │
│       │              Scope=Upstream, no block)      │
│       │            → two ranked lists               │
│       ▼                                             │
│  User picks item OR "abbrechen"                     │
│       │                                             │
│       ▼                                             │
│  emhass-cross-repo-flow (NEW, skill, Type-1 only)   │
│       │                                             │
│       │ 1. Routing-Mini-Assessment                  │
│       │    → brainstorm | plan-light | direct       │
│       │                                             │
│       │ 2. Spec (always) → docs/superpowers/specs/  │
│       │ 3. Plan (always) → docs/superpowers/plans/  │
│       │                                             │
│       │ 4. Board-card Status: Todo → In Progress    │
│       │                                             │
│       │ 5. Handoff-Prompt section in plan.md        │
│       │    User opens new session in                │
│       │    claude-code/emhass/, copy-paste prompt   │
│       │                                             │
│       │ 6. Fork-session implements → opens PR       │
│       │    Returns HANDOFF-RESULT block             │
│       │    Board-card → Review                      │
│       │                                             │
│       │ 7. On PR merge:                             │
│       │    → emhass-board-merge-bookkeeping         │
│       │      (existing skill, unchanged for merge   │
│       │       path; minor extension for closed-     │
│       │       not-merged path — see §11)            │
│       │    → Board: In Progress/Review → Done       │
│       │                                             │
│       │ 8. Skill end: "pick next item? (j/n)"       │
│       │    Halbautomatisch — user chooses           │
│       │    On "j" → loop back to picker             │
│       │                                             │
│       └─ Pivot pathways:                            │
│          (a) Fork-session: plan diverges            │
│              → "blocked" status, Pivot Reason       │
│              appended to plan.md, board → Todo      │
│              main-session presents re-plan options  │
│          (c) PR closed-not-merged                   │
│              → bookkeeping with Won't Do mode       │
└─────────────────────────────────────────────────────┘
```

## 5. Component responsibilities

| Component | Responsibility | Out-of-scope for component |
|-----------|---------------|---------------------------|
| `board/next.py` (script) | Filter + rank + render output (md or json) | No skill-conversation, no side effects, no GitHub API calls |
| `emhass-next-item-picker` (skill) | Present script output, accept user pick, hand off to flow | No implementation, no plan, no item-content reasoning |
| `emhass-cross-repo-flow` (skill) | Routing assessment, spec/plan generation (or invocation of brainstorming/writing-plans), handoff-prompt assembly, board status updates, pivot orchestration, loop-end prompt | Picker logic, post-merge bookkeeping mutations, fork-side implementation |
| `emhass-board-merge-bookkeeping` (skill, existing — minor extension) | Post-merge OR closed-not-merged board cleanup | Pre-merge anything |

## 6. File layout

```
emhass-contributions/
├── .claude/
│   └── skills/
│       ├── emhass-board-merge-bookkeeping/    # existing, +closed-not-merged mode
│       │   └── SKILL.md
│       ├── emhass-cross-repo-flow/            # NEW
│       │   ├── SKILL.md
│       │   └── templates/
│       │       ├── spec.md.tpl                # used for plan-light path; brainstorm path delegates to superpowers:brainstorming
│       │       └── handoff-prompt.md.tpl      # appended to plan.md after writing-plans produces it
│       └── emhass-next-item-picker/           # NEW
│           └── SKILL.md
├── board/
│   ├── items.json                              # source of truth (existing)
│   ├── lib.py                                  # existing helpers
│   ├── fetch.py                                # existing
│   └── next.py                                 # NEW — picker logic
├── tests/
│   ├── fixtures/
│   │   └── items_sample.json                   # NEW — picker test fixture
│   └── test_board_next.py                      # NEW — pytest unit tests
└── docs/superpowers/
    ├── specs/
    │   └── 2026-05-07-emhass-cross-repo-flow-design.md  # this spec
    └── plans/
        └── 2026-05-07-emhass-cross-repo-flow.md         # implementation plan (next step)
```

**Naming conventions:**

| Artifact | Path pattern | Example |
|----------|-------------|---------|
| Spec | `docs/superpowers/specs/YYYY-MM-DD-<board-id>-design.md` | `2026-05-07-ac-2a-design.md` |
| Plan | `docs/superpowers/plans/YYYY-MM-DD-<board-id>.md` | `2026-05-07-ac-2a.md` |
| Branch (fork) | `<type>/<board-id-or-issue>-<slug>` | `feat/ac-2a-unit-field` |
| Bookkeeping script | `board/YYYY-MM-DD-pr-N-merged.py` | (existing, unchanged) |

**Templates:** stored as separate `.md.tpl` files (not inline in SKILL.md). Reasoning: SKILL.md stays focused on logic (~250-300 lines); templates are sizable markdown bodies (Spec ≈ 40-80 lines for mini-form, Handoff-Prompt ≈ 60-80 lines) that benefit from independent edit cycles after first live-runs reveal refinement needs. Skill performs simple `{{placeholder}}` string-replace; no templating engine. Plan body itself is delegated to `superpowers:writing-plans` (no template needed); brainstorm-spec body delegated to `superpowers:brainstorming` (also templated by that skill, not us).

## 7. Trigger phrases

### `emhass-cross-repo-flow`

Fires on:
- User names a board item ID + intent to work on it ("lass uns AC-2a angehen", "let's do AG-7", "starten wir ag-b1")
- User names an issue number + PR intent ("issue #826 angehen", "PR für 824 vorbereiten", "auf goodwill #343 fixen")
- Generic intent phrases when item context is clear from prior turn ("ich will PR machen für …", "lass uns das nächste angehen" directly after picker output)

Does NOT fire on:
- Type-2 items (audit writing, RFC writing) — out of scope
- "What's next?" without item — that's the picker
- "Write the bookkeeping script" — that's `emhass-board-merge-bookkeeping`

### `emhass-next-item-picker`

Fires on:
- "Was kommt als nächstes?" / "what's next" / "what should I work on"
- "Quick wins?" / "schnelle Sachen?"
- "Strategic next" / "großes Item next"
- "Show me the board" / "zeig was offen ist"
- Halbautomatic chained call from `emhass-cross-repo-flow` end

Does NOT fire on:
- User already named a concrete item — go straight to flow
- "Liste mir alle bugs" — picker default-filters bugs

### Disambiguation

If both could match (e.g. "lass uns nächstes Item angehen"): if no concrete item named → picker first. Description text in YAML frontmatter explicitly distinguishes ("user wants to identify" vs. "starting work on … item").

## 8. `board/next.py` — picker script

### CLI

```bash
python board/next.py \
  [--mode=quickwin|strategic|both]   # default: both
  [--include-bugs]                    # default: off
  [--scope=upstream|local|both]       # default: upstream
  [--limit=N]                         # default: 5 per list
  [--format=md|json]                  # default: md
```

### Filter rules (always applied)

| Rule | Source |
|------|--------|
| `Status` = `Todo` (not In Progress / Review / Done / Won't Do) | items.json field |
| Skip if sibling-PR card with `Status: Review` exists | items.json related items |
| Skip if body contains `Blocked-by: <id>` and blocker not Done | items.json body |
| Skip bug-label upstream issues unless `--include-bugs` | item type=link + repository=davidusb-geek/emhass + label=bug |
| Skip if `Scope` ≠ filter value | items.json field |

### Ranking

**Quick-Win list:**
- Pre-filter: `Effort` ∈ {`XS`, `S`}
- Sort: `Phase` asc → `Priority` asc → `Effort` asc → `id` asc

**Strategic list:**
- Pre-filter: `Priority` ∈ {`P0`, `P1`}
- Sort: `Priority` asc → `Phase` asc → `Effort` asc → `id` asc

### Markdown output (default)

```markdown
# Next emhass items — 2026-05-07

## Quick wins (Effort XS/S, Todo, no block)

| ID | Goal-fit | Title | Phase | Pri | Effort | Why quick |
|----|----------|-------|-------|-----|--------|-----------|
| AC-2a | LLM-ready | Add structured `unit` field to param_definitions.json | 1 | P1 | S | linked #826, schema-only, no logic |
| AC-1 | LLM-ready | Document plan/optimization output column schema | 1 | P1 | S | linked #828, docs only |

## Strategic next (P0/P1, lowest Phase)

| ID | Goal-fit | Title | Phase | Pri | Effort | Why strategic |
|----|----------|-------|-------|-----|--------|---------------|
| AC-2a | LLM-ready | Add structured `unit` field … | 1 | P1 | S | first AC-2 follow-up after AC-2-fix merged |
| EV-1 | EV-EVCC | Persistent flexible-load registry | 3 | P0 | M | unblocks #824 corridor |
```

JSON output: same data in machine-readable form for `emhass-next-item-picker` skill consumption.

### Goal-fit derivation

Order: (i) `Goal` field on the item if present (rich source-of-truth, optional schema extension); (ii) ID-prefix heuristic (`AC-*` → LLM-ready, `EV-*` → EV-EVCC); (iii) empty if neither applies. Items.json schema does not need migration today; (i) is opt-in.

### "Why quick" / "Why strategic" generation

Deterministic string templates from item fields + body markers (e.g. `linked #N` if body contains an issue link, `audit-derived` if body references `audits/`). No LLM-generated reasoning.

### Edge cases

- Empty list → render `_(no items match these criteria)_`
- All items in PR-Review → output "Picker empty — everything in flight, wait for merges"
- Item appears in both lists → present in both with appropriate Why tag

## 9. Spec template — Mini and Full forms

Same skeleton, content depth scales by routing path.

```markdown
# {{board_id}} — {{title}} — Design

**Date:** {{YYYY-MM-DD}}
**Card:** `{{board_id}}` (board/items.json)
**Issue:** #{{issue_number}}  *(if present)*
**Audit source:** `audits/{{audit_path}}` *(optional)*
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Branch:** `{{type}}/{{branch_slug}}`
**Effort:** {{effort}}
**Phase / Priority:** Phase {{phase}} / {{priority}}
**Goal-fit:** {{goal_fit}}

## 1. Problem
## 2. Goal
## 3. Decisions
## 4. Files touched
## 5. Concrete edits
## 6. Test strategy
## 7. Acceptance criteria
## 8. Out of scope
## 9. References
```

| Section | Mini-form (plan-light) | Full-form (brainstorm) |
|---------|------------------------|------------------------|
| Problem | 2-4 sentences | up to ~200 words, examples |
| Goal | 1 sentence | 1 paragraph |
| Decisions | 1-3 rows ("from issue body" / "from audit") | full brainstorming decision table |
| Files touched | list | list + adjacent files explicitly NOT edited |
| Concrete edits | inline table 5-10 rows | per-file before/after sections |
| Test strategy | 1 paragraph | test matrix |
| Acceptance | 3-5 bullets | full checklist |
| Out of scope | optional | required |
| References | primary source only | all linked |

Approximate lengths: Mini ≈ 40-80 lines, Full ≈ 150-250 lines.

### Who writes the spec

- **Routing=brainstorm:** `superpowers:brainstorming` skill produces spec via existing flow → writes to `docs/superpowers/specs/`. `cross-repo-flow` invokes it; doesn't reimplement.
- **Routing=plan-light:** `cross-repo-flow` writes spec directly via `templates/spec.md.tpl`. Inputs: item from picker / user-named, optional audit/RFC path, optional issue body. Skill fills placeholders from these sources.
- **Routing=direct:** no spec, no plan; only handoff-prompt with embedded micro-rationale. Reserved for 1-line edits / doc typos. Handoff references issue/card directly.

### Plan body

`superpowers:writing-plans` skill produces plan body in established AG-7-style (Goal, Architecture, Tech Stack, File Structure, Task-by-task with checkboxes). `cross-repo-flow` post-processes by appending `## Handoff-Prompt` section and triggering board-card status transition (Todo → In Progress).

## 10. Handoff-prompt template

Lives as `## Handoff-Prompt` section appended to plan.md. Inside that section, the copy-paste-ready block in a fenced codeblock (so user can copy verbatim into a new Claude Code session in the fork repo).

### Template content

```markdown
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
- Spec: `{{spec_relative_path_from_contributions_root}}`
- Plan: `{{plan_relative_path_from_contributions_root}}`

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
````

After Fork-Session reports HANDOFF-RESULT, return to the main planning session and paste
the result block. Main session will:
- On `pr-open`: update Board-Card to `Status: Review`
- On `blocked`: read appended Pivot Reason, re-plan
- On `failed`: triage, decide
```

### Key properties

1. Paths relative to fork working dir (`../emhass-contributions/...`) — both repos are sibling folders under `claude-code/`
2. Branch name pre-determined by main-session — fork session must NOT invent (per `feedback_branch_naming` memory)
3. Strict return contract — fixed `HANDOFF-RESULT <id>` format for parseable handoff back
4. PR-first anchored — no "let's open RFC first" path. Pivot only for technical-plan-wrong, not "maybe idea is bad" (per `feedback_pr_first_for_strategic` memory)
5. Pre-flight identical to `emhass-board-merge-bookkeeping` auth hygiene
6. PR-body skeleton generated from spec sections 1+2+9 + issue link — no LLM padding

### What is NOT in the handoff prompt

- Skill-system explanations, memory structure, user profile
- Brainstorm/decision history (that's in spec)
- Picker output / other items
- Bookkeeping instructions (explicitly main-session-only)

## 11. Routing-Mini-Assessment

First phase after skill trigger. Skill reads item context, presents structured assessment, asks user. If user silent → recommended path proceeds.

### Sources read (in order)

1. Board-item in `items.json` — fields Status, Phase, Priority, Effort, Scope, Category, body
2. Linked issue (if any) — `gh issue view <N> --repo davidusb-geek/emhass --json title,body,labels,comments,author`
3. Existing audit/RFC if body references one (`audits/...md` or `rfcs/...md`) — read file
4. Existing spec/plan in `docs/superpowers/{specs,plans}/*.md` matching board-id — item already in flight, different path

### Signals → path mapping

| Signal | Value | Implication |
|--------|-------|-------------|
| Bug-label on linked issue | true | Hard-stop: only proceed on explicit user opt-in (per `feedback_no_auto_bugfix`). Skill MUST ask "goodwill or eigen-betroffen?" |
| Existing audit/RFC | present | Findings + reasoning already documented → `plan-light` recommended |
| Maintainer engagement | owner commented in last 14d with solution direction | `plan-light` (task is well-defined) |
| Maintainer linked PR as solution | true | Hard-stop: "item already in flight upstream — really proceed in parallel?" |
| Goal-fit | EV-EVCC or LLM-ready, no audit/RFC | `brainstorm` (strategic, **PR-first** — per `feedback_pr_first_for_strategic`) |
| Goal-fit | Infra/null, no audit/RFC | `brainstorm` with "really worth doing?" check |
| Effort | XS, clearly-defined 1-3-line edit, doc typo | `direct` (no spec/plan, direct handoff) |
| Existing spec without plan | true | Resume at writing-plans, not new |
| Existing spec + plan | true | Resume at executing (regenerate handoff) or check pivot |

### Output to user (sample)

```markdown
## Routing-Assessment für AC-2a

**Item-Snapshot:**
- Title: Add structured `unit` field to param_definitions.json
- Phase 1 / P1 / Effort S
- Goal-fit: LLM-ready
- Linked issue: #826 (open, no maintainer comment, no PR linked)
- Existing audit: audits/2026-04-28-param-definitions.md (referenced in body)
- Spec/Plan: none yet

**Signals:**
- Audit findings exist → reasoning documented
- LLM-ready Goal-fit → strategic corridor
- No maintainer engagement → PR-first memory applies
- Effort S → fits one fork-session

**Recommended path: `plan-light`**

Reason: Audit already has problem + findings. Decisions reduce to "adopt
audit recommendation 1:1?" — no brainstorm depth needed. PR-first: no RFC,
direct Spec → Plan → PR.

**Alternatives (override with "brainstorm" / "direct" / "abbrechen"):**
- `brainstorm`: only if you want to question the audit recommendation
- `direct`: not recommended — even compact schema change deserves a Mini-Spec for PR body
- `abbrechen`: if item-snapshot suggests not the right time

Welcher Pfad?
```

### User-response handling

- `"plan-light"` / `"go"` / `"empfohlen"` → recommended path
- `"brainstorm"` → invokes `superpowers:brainstorming` with pre-loaded context
- `"direct"` → handoff-prompt only, no spec/plan
- `"abbrechen"` / `"stop"` → exit, no board update
- Content question → skill answers, asks again

### Bug special-case

```markdown
## Routing-Assessment für #343

**Item-Snapshot:**
- Bug-Label: true
- `feedback_no_auto_bugfix` applies — bugs not in standard goal-stream

Before routing: why this bug?
- (a) goodwill PR for maintainer trust
- (b) eigen-betroffen (e.g. battery setup)
- (c) other reason

Sag (a)/(b)/(c) bevor ich weiter assesse.
```

User answer unlocks rest of routing.

### Strategic-item special-case (PR-first)

```markdown
**PR-first memory applies.**

Strategic item without maintainer engagement → no RFC-first path.
Recommend: `brainstorm` with output = direct spec for code PR. Skip RFC.

If you really want RFC first (unclear scope, etc.) → explicit override: "rfc-first".
RFC-first only acceptable if maintainer has explicitly engaged on issue/discussion
or open corridor-block exists.
```

## 12. Pivot pathways

### Pivot (a) — plan is wrong (fork-session-discovered)

**Trigger in fork-session:** plan assumption diverges from upstream code reality.

**Fork-session actions** (per handoff-prompt contract):
1. Stop, no improvisation
2. No push, no partial commit
3. Append `## Pivot Reason` section to `../emhass-contributions/{{plan_relative_path}}`:
   ```markdown
   ## Pivot Reason — 2026-05-08

   **Status:** blocked
   **Discovered at:** Plan Task {{N}}, Step {{M}}

   **Divergence:**
   - Plan expects: {{exact citation}}
   - Reality: `{{file:line}}` shows {{actual}}
   - Why this breaks the plan: {{1-2 sentences}}

   **Suggested re-plan direction (optional):**
   {{1-3 bullets or "main session must decide"}}
   ```
4. No branch push; branch stays local
5. Return:
   ```
   HANDOFF-RESULT {{board_id}}
   status: blocked
   pr-url: none
   branch: {{branch_name}}
   tests: skipped
   notes: plan diverges from upstream — see Pivot Reason in plan.md
   ```

**Main-session actions on `status: blocked`:**

1. Auth check — switch to OptimalNothing90 if needed (for board)
2. Re-read plan.md — specifically `## Pivot Reason` section
3. Board update — Status back to `Todo` (no `Blocked` status exists; `Todo` with note)
4. Brief user with three options:
   - **Re-plan in place** — invoke `superpowers:writing-plans` again with updated context. Old plan stays as audit trail with `[SUPERSEDED-BY: <new-plan-path>]` marker.
   - **Spec revision** — if divergence touches design assumptions, re-enter brainstorming for that decision only. Spec gets `## Revisions` section appended.
   - **Drop item** — if upstream reality makes work irrelevant, mark Won't Do, document, exit.
5. User chooses → corresponding path

**What does NOT happen on (a):**
- No auto-re-plan without user confirmation
- No fork-side branch deletion (user manages)
- No bookkeeping invocation (item not done)

### Pivot (c) — PR closed-not-merged

**Trigger:** maintainer closes PR without merge. Detected via `gh pr view <N> --json state,mergedAt`:
- `state=MERGED` → normal path
- `state=CLOSED, mergedAt=null` → pivot (c)

User can also bring this manually: "PR #N wurde geschlossen, nicht gemerged".

**Actions:**

1. Auth check — OptimalNothing90 active
2. Read maintainer comments: `gh pr view <N> --repo davidusb-geek/emhass --comments` — last 1-3 comments, especially owner
3. Brief user:
   ```markdown
   ## PR #N — closed without merge

   Maintainer comment (most recent):
   > {{comment_excerpt}}

   Three options:
   - **Won't Do:** maintainer signals no-go. Bookkeeping with `Status: Won't Do`
     for board-card and PR-sibling. Spec/Plan stay as documented history.
   - **Re-do with changes:** maintainer wants different approach. Re-enter
     routing → likely `brainstorm` with lessons-learned. New PR later.
   - **Wait & escalate:** unclear reason, ask maintainer (issue comment, discussion).
     Item stays `Review`, no bookkeeping yet.

   Which?
   ```
4. **On Won't Do:** trigger bookkeeping skill with `won't-do` mode flag. Board-card and PR-sibling both → `Won't Do`.
5. **On Re-do:** spec gets `## Revisions` section with maintainer feedback quote. Plan superseded (`[SUPERSEDED-BY: ...]`). Routing phase restarts.
6. **On Wait:** skill exits, board unchanged.

### Bookkeeping skill extension for (c)

Existing `emhass-board-merge-bookkeeping` only handles merge path. Extension chosen:

**Approach:** existing skill gets mode-switch in description. Description grows to:
```yaml
description: Use when an upstream emhass PR is merged OR closed-without-merge ...
```

Script template adds `Status: Won't Do` value option. Skill MD grows by ~30 lines, no new skill.

**Why not separate skill:** would duplicate ~70% of merge bookkeeping. Board already has `Won't Do` as Status option; field-mapping logic identical, only values differ.

### Out of scope (per Decision #8)

- **(b) PR review iteration** — maintainer requests changes, no close. User edits plan/code manually, fork-session re-runs on same branch. No skill aid. Accepted.
- **(d) parallel items** — user may have two items in flight. Board shows two `In Progress`. Self-discipline. No skill conflict.

## 13. Test strategy

Three layers: unit (script), self-test (skills), live-run acceptance.

### 13.1 Unit tests for `board/next.py`

- pytest (already in dev deps via `.pre-commit-config.yaml`)
- Fixture: `tests/fixtures/items_sample.json` — hand-curated mini items.json (~15 items) covering all filter/ranking edge cases
- Tests in `tests/test_board_next.py`

Required test cases:

| Test | Expectation |
|------|-------------|
| `test_filter_excludes_done_items` | items with Status=Done absent |
| `test_filter_excludes_in_progress` | items with Status=In Progress absent |
| `test_filter_excludes_review_siblings` | item with sibling-PR in Review absent |
| `test_filter_excludes_bug_label_default` | upstream-issue with bug-label absent without `--include-bugs` |
| `test_filter_includes_bug_label_with_flag` | …present with flag |
| `test_filter_blocked_by_marker` | body marker `Blocked-by: X` filters when X not Done |
| `test_quickwin_only_xs_s` | Quick-Win list has only Effort XS or S |
| `test_strategic_only_p0_p1` | Strategic list has only P0 or P1 |
| `test_quickwin_sort_order` | Phase asc → Priority asc → Effort asc → id asc |
| `test_strategic_sort_order` | Priority asc → Phase asc → Effort asc → id asc |
| `test_goal_fit_field_wins` | item with `Goal: LLM-ready` field → tag = LLM-ready |
| `test_goal_fit_prefix_fallback` | item without field, ID `AC-3` → fallback LLM-ready |
| `test_empty_lists_render_placeholder` | no Quick-Wins → output contains "(no items match)" |
| `test_json_output_schema` | `--format=json` produces validatable structure |

Pre-commit hook adds `pytest tests/test_board_next.py` to existing config.

### 13.2 Skill self-tests (pattern from `emhass-board-merge-bookkeeping`)

Each new skill gets `## Self-test (one-shot, at first use after this skill was authored)` section in SKILL.md with `STATUS: PENDING` marker. First live-run (subagent or user) executes, documents outcome, flips marker to `STATUS: DONE`.

**`emhass-cross-repo-flow` self-test:**
- Target: a low-stakes XS audit-followup (e.g. typo fix in param_definitions.json description text)
- Sequence: Routing-Assessment → user picks `plan-light` → spec written → plan via writing-plans → handoff-prompt generated → fork branch created but **not pushed** → skill aborts before PR-open
- Pass: all artifacts at expected paths, branch name correct, pre-flight checks ran, board-card moved to In Progress
- Cleanup: board-card back to Todo, spec/plan deleted or marked `_self-test_`

**`emhass-next-item-picker` self-test:**
- Script runs against live `items.json`
- Skill renders output markdown
- Pass: ranked lists appear, filters visible, no bug-label item in default list
- Idempotency: two runs produce identical output (modulo date header)

Self-test is final task in the implementation plan.

### 13.3 Live-run acceptance

First end-to-end real run observed against:

| Check | Pass criterion |
|-------|---------------|
| Picker → flow chaining | "ja, weiter" → cross-repo-flow starts without re-setup |
| Spec path | file at expected path |
| Plan path | file at expected path, contains `## Handoff-Prompt` section |
| Branch name | matches `<type>/<board-id>-<slug>` exactly |
| Board status transitions | Todo → In Progress (after plan), → Review (after PR-open) |
| Handoff contract | fork-session sees all required fields, can read plan from `../emhass-contributions/` |
| Return block | fork-session HANDOFF-RESULT block parseable |
| Bookkeeping trigger | `gh pr view` MERGED → bookkeeping auto-invokes |
| Loop prompt | after bookkeeping, "next item?" appears |
| Pivot (a) | provoked plan error → Pivot Reason appended, status blocked, re-plan options shown |

**First live-run candidate:** AC-2a (Add structured `unit` field). Effort S, audit exists (`audits/2026-04-28-param-definitions.md`), no bug label, LLM-ready goal-fit, issue #826 open without maintainer engagement. Ideal plan-light path.

### 13.4 Out of test-scope (YAGNI)

- No integration tests mutating real GitHub API (board, PRs) — manual self-test sufficient
- No fuzzing of routing heuristic — adaptive mode makes mis-routing user-overridable
- No load tests of picker — items.json has <50 items
- No cross-platform tests — Windows is primary, MacOS/Linux not targeted

## 14. Acceptance criteria

- [ ] `board/next.py` exists; CLI matches §8; all 14 unit tests pass
- [ ] `tests/fixtures/items_sample.json` and `tests/test_board_next.py` exist; pytest runs clean
- [ ] Pre-commit config runs `pytest tests/test_board_next.py`
- [ ] `.claude/skills/emhass-next-item-picker/SKILL.md` exists with description matching §7
- [ ] `.claude/skills/emhass-cross-repo-flow/SKILL.md` exists with description matching §7
- [ ] `.claude/skills/emhass-cross-repo-flow/templates/{spec,handoff-prompt}.md.tpl` exist (plan body delegated to `superpowers:writing-plans`, brainstorm-spec delegated to `superpowers:brainstorming`)
- [ ] `.claude/skills/emhass-board-merge-bookkeeping/SKILL.md` extended for closed-not-merged path (description + Won't Do mode in script template)
- [ ] First skill self-test for `emhass-cross-repo-flow` completes successfully against XS test item, marker flipped to `STATUS: DONE`
- [ ] First skill self-test for `emhass-next-item-picker` completes successfully against live `items.json`, marker flipped to `STATUS: DONE`
- [ ] Live-run acceptance against AC-2a from picker → board update → handoff → fork session → PR-open passes all checks in §13.3
- [ ] All design decisions in §3 implemented as described

## 15. Out of scope

- Type-2 (audit/RFC writing) and Type-3 (local-only code) item orchestration — handled ad-hoc, may get separate skills later
- Vollautomatic loop chaining without user confirmation — explicitly halbautomatic per Decision #7
- Auto-pickup in fork-session via marker files — explicitly manual copy-paste per §4 architecture
- Cross-session FS state synchronization — board is single source of truth (Decision #9)
- PR review iteration helper — left manual (Decision #8 (b))
- Parallel item slot management — left as user self-discipline (Decision #8 (d))
- LLM-generated branch names, PR titles, commit messages — all deterministic per Decision #11
- Schema migration of `items.json` to add `Goal` field — opt-in per item, not forced

## 16. References

- Existing skill: `.claude/skills/emhass-board-merge-bookkeeping/SKILL.md`
- Board source-of-truth: `board/items.json`, `board/lib.py`, `board/fetch.py`
- Existing spec/plan examples (Type-1 items):
  - `docs/superpowers/specs/2026-04-30-ac-2-fix-design.md` (mini-form)
  - `docs/superpowers/specs/2026-04-30-ag-7-agents-md-design.md` (full-form)
  - `docs/superpowers/plans/2026-04-30-ag-7-agents-md.md` (full plan reference)
- Memory entries that drive skill behavior:
  - `feedback_no_auto_bugfix.md` — bug default-skip
  - `feedback_pr_first_for_strategic.md` — PR-first for strategic items
  - `feedback_branch_naming.md` — deterministic branch naming
  - `project_strategic_goals.md` — LLM-ready + EV-EVCC goal streams
  - `project_user_has_battery.md` — battery items have direct user impact
- Superpowers skills used: `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:executing-plans`, `superpowers:subagent-driven-development`, `superpowers:verification-before-completion`
