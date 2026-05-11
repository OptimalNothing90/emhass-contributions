# AG-onboarding — AI-coder Contributor Onboarding Doc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `docs/develop_ai_coders.md` — a ~1500-word caveman-full-style human-facing companion to AGENTS.md teaching AI-coder contributors EMHASS-specific landmines (sign conventions, SOC scaling, MILP infeasibility, q_input_start=0, dual logger, OptimizationCacheKey, source-resolve discipline) + decision-tree for issue-first-vs-PR-direct + pre-PR self-check + red-flags + help-resources, cross-linked from CONTRIBUTING.md + AGENTS.md preamble + Sphinx toctree.

**Architecture:** Single new Markdown file under existing flat `docs/` tree. Three minimal cross-link edits to existing files (CONTRIBUTING.md +1 line, AGENTS.md preamble +1 italics-line, toctree +1 entry). No new Sphinx dependencies, no new subfolders, no new tooling. Source-traced landmines (each carries `src/emhass/...:LINE` or PR-ref citation) per `feedback_source_resolve_first`.

**Tech Stack:** Markdown (MyST flavor for Sphinx), ASCII-art tree in fenced code block, real upstream PR-refs for click-through teaching. No code, no tests, no config.

**Spec source:** `../emhass-contributions/docs/superpowers/specs/2026-05-11-ag-onboarding-design.md`
**Corridor:** [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) (Layer-1 AI-coder-friendly docs)
**Hard-dep (merged):** PR [#831](https://github.com/davidusb-geek/emhass/pull/831) AGENTS.md introduction (2026-04-30)

---

## Pre-flight (run once before Task 1)

- [ ] **P1: Verify working directory is the fork repo**

```bash
git rev-parse --show-toplevel
```
Expected: `C:/Users/MauricioSchäpers/claude-code/emhass`.

- [ ] **P2: Verify upstream remote + sync master**

```bash
git remote -v
git fetch upstream
git checkout master
git merge --ff-only upstream/master
```
Expected: `origin` → `OptimalNothing90/emhass`, `upstream` → `davidusb-geek/emhass`; master fast-forwards or already up-to-date.

- [ ] **P3: Verify active GitHub account**

```bash
gh auth status
```
Expected: `OptimalNothing90` active. Switch with `gh auth switch --user OptimalNothing90` if not.

- [ ] **P4: Clean tree**

```bash
git status --short
```
Expected: empty.

---

## Task 1: Create branch + source-trace verification for landmines

**Files:** read-only inspection of upstream EMHASS source

Spec D13 requires each landmine in Section 3 to carry a file:line OR PR-ref citation. Verify the citations are still valid against current upstream before writing them into the doc.

- [ ] **Step 1.1: Create branch**

```bash
git checkout -b docs/ag-onboarding
```

- [ ] **Step 1.2: Confirm AGENTS.md exists at repo root**

```bash
test -f AGENTS.md && head -5 AGENTS.md
```
Expected: file exists, frontmatter shows `name: emhass-agents`. If missing: STOP, append `## Pivot Reason` — AG-7 dependency unmet.

- [ ] **Step 1.3: Confirm CONTRIBUTING.md exists**

```bash
test -f CONTRIBUTING.md && cat CONTRIBUTING.md
```
Expected: file exists, contains line `For AI coding agents working on EMHASS source, see [\`AGENTS.md\`](AGENTS.md).` (or similar wording mentioning AGENTS.md).

- [ ] **Step 1.4: Verify SOC ×100 scaling citation**

```bash
grep -n 'SOC_opt.*\* *100\|"SOC_opt".*\* *100' src/emhass/command_line.py
```
Expected: at least 1 match around line ~2329. Note actual line number for Section-3 citation.

- [ ] **Step 1.5: Verify dual-logger evidence**

```bash
grep -c "logger\." src/emhass/command_line.py
grep -c "logger\." src/emhass/web_server.py
```
Expected: both > 5. Confirms both files have substantive logger usage (dual-subsystem claim valid).

- [ ] **Step 1.6: Verify OptimizationCacheKey exists**

```bash
grep -rn "OptimizationCacheKey" src/emhass/
```
Expected: matches in at least one source file. Note file:line for Section-3 citation. If zero matches: the constant may have been renamed since the item body was written — note new name OR drop the landmine.

- [ ] **Step 1.7: Verify PR #785 referenced is the q_input_start fix**

```bash
gh pr view 785 --repo davidusb-geek/emhass --json title,mergedAt
```
Expected: title mentions `q_input_start` OR thermal-battery infeasibility; `mergedAt` is non-null (PR was merged). If wrong PR: search `gh pr list --repo davidusb-geek/emhass --search "q_input_start"` and use the correct number.

- [ ] **Step 1.8: Verify the 5 example PRs for decision-tree teaching**

```bash
for pr in 817 814 835 836 830 831; do
  gh pr view "$pr" --repo davidusb-geek/emhass --json number,state,mergedAt,title --jq '"#\(.number) \(.state) \(.title)"'
done
```
Expected: 6 lines, all valid PRs. #817 / #814 / #831 should be MERGED. #835 / #836 / #830 should be OPEN (those are our in-flight PRs). If any returns 404: drop that example or substitute, document substitution in `## Pivot Reason`.

- [ ] **Step 1.9: Confirm the toctree owner for `develop`**

```bash
grep -rn "^develop$\|^develop\.md$" docs/*.md
```
Expected: at least 1 file has `develop` (or `develop.md`) as a standalone toctree entry. Note which file owns it (likely `docs/index.md` or `docs/section_reference.md`). Task 9 will edit that file.

- [ ] **Step 1.10: Halt-on-drift check**

If any of Steps 1.2-1.9 returns unexpected (AGENTS.md missing, SOC ×100 line drifted by > 50 lines, dual-logger evidence absent, PR #785 not about thermal-battery, example PRs returning 404, no toctree found): STOP. Append `## Pivot Reason` to this plan with concrete divergence facts. Report back via HANDOFF-RESULT `status: blocked`.

- [ ] **Step 1.11: No commit**

Discovery-only task. Citations get embedded in Section 3 in Task 4 below.

---

## Task 2: Write Intro + Section 1 (AI-Tool-Setup)

**Files:**
- Create: `docs/develop_ai_coders.md`

- [ ] **Step 2.1: Create the file with Intro + Section 1**

Create `docs/develop_ai_coders.md` with this exact content:

````markdown
# AI-coder contributor onboarding

Companion to [`docs/develop.md`](develop.md) (humans, general) and [`AGENTS.md`](../AGENTS.md) (vendor-neutral rules for AI agents). Read develop.md first if new to EMHASS.

This file teaches the **human driving the AI agent**. AGENTS.md teaches the agent. develop.md teaches the human contributing without an agent. Three audiences, three docs, no overlap.

EMHASS landmines AI tools won't flag without explicit prompt: sign conventions, SOC scaling, MILP infeasibility, `q_input_start=0`, dual logger, `OptimizationCacheKey`, source-resolve discipline. Each section below addresses one.

## 1. AI-tool setup

### 1a. Claude Code (primary, tested-against)

Native tools cover context-loading on-demand. No pre-pack step.

| Action | Approach |
|---|---|
| Load file | `Read` tool |
| Find files | `Glob` pattern |
| Search content | `Grep` regex |
| Run tests | `Bash`: `pytest tests/` |
| Lint | `Bash`: `uvx ruff check .` |
| PR ops | `Bash`: `gh pr create`, `gh pr view`, `gh pr edit` |
| Format | `Bash`: `uvx ruff format .` |

Per-task agent choice:
- Refactor / implement → general agent with `Edit` + `Write`
- Code review → `code-reviewer` agent (read-only)
- Codebase exploration → `Explore` agent or `Glob` + `Grep` direct

Public EMHASS-specific skill plugin: TBD when board item AG-B1 ships. Until then, hand-instruct the agent from AGENTS.md.

### 1b. Cursor (untested — contribution welcome)

Conventions seen in community:
- `@file` mention to add context to chat
- `pytest tests/` passes locally before commit
- `uvx ruff check .` clean before push

PR adding a tested Cursor-setup recipe for EMHASS welcome.

### 1c. Aider (untested — contribution welcome)

Conventions seen in community:
- `/add <file>` to add context
- `/test` and `/lint` if configured in `.aider.conf.yml`
- Same pytest + ruff baseline

PR adding a tested Aider-setup recipe welcome.
````

- [ ] **Step 2.2: Word count check (cumulative)**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: ~300-350 words (Intro ~70 + Section 1 ~250-280).

- [ ] **Step 2.3: Commit**

```bash
git add docs/develop_ai_coders.md
git commit -m "docs(ai-coders): add Intro + Section 1 AI-tool-setup"
```

---

## Task 3: Append Section 2 (Decision-Tree)

**Files:**
- Modify: `docs/develop_ai_coders.md`

- [ ] **Step 3.1: Append Section 2**

Append to `docs/develop_ai_coders.md`:

````markdown

## 2. Decision-tree: issue-first vs PR-direct

Default mental model:

```
What kind of change?
│
├── Pure docs / typo / wording                  → PR direct
├── Doc reorg / new doc / structural rename     → Issue or Discussion first
├── Bug fix < 10 lines, no behavior change      → PR direct (reproducer in body)
├── Bug fix ≥ 10 lines OR behavior change       → Issue first → then PR
├── New feature / new endpoint / new param      → Issue first (always)
└── Refactor (no behavior change)               → Issue first if > 50 LOC, else PR direct
```

Real-PR examples:

- **PR-direct (small docs / typo):** [#817](https://github.com/davidusb-geek/emhass/pull/817) (regression_model typo, 2 lines), [#814](https://github.com/davidusb-geek/emhass/pull/814) (broken doc link).
- **Issue-first (structural new doc):** [#835](https://github.com/davidusb-geek/emhass/pull/835) filed [issue #828](https://github.com/davidusb-geek/emhass/issues/828) first for the plan-output schema doc.
- **Discussion-first variant (corridor-aligned):** [#836](https://github.com/davidusb-geek/emhass/pull/836) (Cookbook scaffold, [Discussion #824](https://github.com/davidusb-geek/emhass/discussions/824) approval first); [#831](https://github.com/davidusb-geek/emhass/pull/831) (AGENTS.md introduction, [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) corridor first).
- **Cautionary (no issue first, got pushback):** [#830](https://github.com/davidusb-geek/emhass/pull/830) param_definitions defaults. No issue filed. Maintainer review revealed direction disagreement (`config_defaults.json` as source vs `param_definitions.json` as source). Result: review round-trip. One-issue-comment first would have surfaced the direction-decision before code edits.
````

- [ ] **Step 3.2: Word count check**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: ~550-650 cumulative (Intro + S1 + S2).

- [ ] **Step 3.3: Commit**

```bash
git add docs/develop_ai_coders.md
git commit -m "docs(ai-coders): add Section 2 decision-tree + real-PR examples"
```

---

## Task 4: Append Section 3 (Landmines with verified citations)

**Files:**
- Modify: `docs/develop_ai_coders.md`

- [ ] **Step 4.1: Re-verify citations against Task 1 source-trace output**

Open the notes from Task 1.4 (SOC ×100 line), 1.5 (logger usage), 1.6 (OptimizationCacheKey location), 1.7 (PR #785 title). Use the actual line numbers found there in the citations below.

- [ ] **Step 4.2: Append Section 3**

Append to `docs/develop_ai_coders.md` (replace `LINE_FROM_TASK_1_4` etc. with the actual line numbers from Task 1):

````markdown

## 3. What AI won't tell you about EMHASS

Seven landmines. AI tools won't flag any of these without explicit prompt.

### Sign conventions
`P_grid`, `P_batt`, `P_PV` are unsigned in DataFrame columns. AI tools guess direction from the variable name. The MILP constraint form locks the sign — variable name does not. Verify against the power-balance constraint in `src/emhass/optimization.py` (battery and grid blocks around the `param_soc_init` plumbing). Trace constraint form, not name.

### SOC scaling trap
`SOC_opt` is fraction (0..1) in the DataFrame and the CSV export. Multiplied by 100 only at the MQTT publish step (`src/emhass/command_line.py:LINE_FROM_TASK_1_4`). Home Assistant entity shows percent; raw CSV row shows fraction. Symmetric trap on input: `soc_init` runtime param expects fraction; most sensors publish percent. See `docs/plan_output_schema.md` once PR #835 merges for the full output-side story.

### MILP infeasibility
"Infeasible" status means the constraint set has no solution. AI tools propose fixes by relaxing arbitrary constraints. Don't. The symptom (infeasibility report) hides the actual wrong constraint. Bisect the constraint set, find the contradiction. Real case: PR [#785](https://github.com/davidusb-geek/emhass/pull/785) traced `q_input_start=0` thermal-battery boundary that made the heat-input schedule unsolvable.

### `q_input_start=0` thermal-battery landmine
Heat-input variable at the first timestep `q_input_start=0` creates infeasibility when thermal-battery state requires non-zero input at t0. Symptom: solve fails with "Infeasible". Cause: initial-state constraint placement. PR [#785](https://github.com/davidusb-geek/emhass/pull/785) carries the fix and the discussion. AI tools that skim `optimization.py` won't catch this — read PR #785's diff before adding thermal-battery-adjacent code.

### Dual logger subsystems
EMHASS has two logger setups: CLI (`src/emhass/command_line.py`) and Web (`src/emhass/web_server.py`). Both substantive (5+ logger calls each — verify via grep). Touch both or none. AI tools that "improve logging" in one file break log-format parity with the other.

### `OptimizationCacheKey` 4-step add-a-param workflow
Adding a new optimisation parameter requires 4 edits per `docs/develop.md`: (1) `src/emhass/data/config_defaults.json`, (2) `src/emhass/static/data/param_definitions.json`, (3) optim helper signature in `command_line.py`, (4) the cache-key tuple. AI tools regularly forget step 4 — silent cache-miss-explosion on every solve. Grep `OptimizationCacheKey` in `src/emhass/` before adding params; verify your new param is in the tuple.

### Source-resolve discipline
Ambiguous types / signs / units / conventions: trace upstream code first. "Ask maintainer" is last resort. Real precedent: PR #835's 7 sign-convention questions self-resolved from `optimization.py` MILP constraints rather than punting to the maintainer. Audit-source-ambiguity does not have to propagate into the PR.
````

- [ ] **Step 4.3: Patch the `LINE_FROM_TASK_1_4` placeholder**

Use the actual line number recorded in Task 1.4. Run:
```bash
grep -n 'SOC_opt.*\* *100\|"SOC_opt".*\* *100' src/emhass/command_line.py
```
Use the first matching line number, e.g. `2329`. Edit `docs/develop_ai_coders.md` to replace `LINE_FROM_TASK_1_4` with that number.

If the line is significantly different from the value committed in Task 4.2 (drift > 5 lines), this is the actual line and the placeholder substitution is the only edit needed. Otherwise the placeholder is fine to leave as the literal `2329` if it matches.

- [ ] **Step 4.4: Word count check**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: ~1000-1100 cumulative.

- [ ] **Step 4.5: Commit**

```bash
git add docs/develop_ai_coders.md
git commit -m "docs(ai-coders): add Section 3 seven EMHASS landmines with source citations"
```

---

## Task 5: Append Section 4 (Self-check pre-PR)

**Files:**
- Modify: `docs/develop_ai_coders.md`

- [ ] **Step 5.1: Append Section 4**

````markdown

## 4. Self-check pre-PR

7-item checklist:

- [ ] Issue filed if behavior change? (Per decision-tree in §2)
- [ ] `pytest tests/` passes locally?
- [ ] `uvx ruff check .` clean?
- [ ] Sign conventions verified (if PR touches power / SOC / cost variables)?
- [ ] One concern per PR (scope discipline)?
- [ ] Issue or Discussion linked in PR body if applicable?
- [ ] Reproducer in body if behavior-change fix?
- [ ] Maintainer-scope-corridors checked? ([Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) Layers, [Discussion #789](https://github.com/davidusb-geek/emhass/discussions/789) MILP scope)
````

- [ ] **Step 5.2: Word count check**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: ~1100-1200 cumulative.

- [ ] **Step 5.3: Commit**

```bash
git add docs/develop_ai_coders.md
git commit -m "docs(ai-coders): add Section 4 pre-PR self-check"
```

---

## Task 6: Append Section 5 (Red flags) + Section 6 (Help-resources) + Footer

**Files:**
- Modify: `docs/develop_ai_coders.md`

- [ ] **Step 6.1: Append Sections 5 + 6 + Footer**

````markdown

## 5. Red flags: stop and ask

Patterns that mean stop, file an issue, do not PR:

- "AI says this is a bug but I can't explain why in my own words." → Don't trust. File issue with the question. Maintainer or community will explain or correct.
- "I can't tell what unit this number is in (W vs kW, fraction vs percent, UTC vs local)." → File issue. Document the ambiguity for the next person.
- "I don't know which subsystem owns this concern (optim vs forecast vs retrieve_hass)." → File issue. Don't pick blindly — cross-subsystem PRs carry heavy review-friction.
- "Test passes but I don't trust the test." → Add a counter-example. If still ambiguous, file issue with the counter-example.
- "AI generated 200+ LOC and I haven't read it line-by-line." → Stop. Read every line before commit. Unreviewed AI-generated code is a future-bug source.

## 6. Help resources

- [GitHub Discussions](https://github.com/davidusb-geek/emhass/discussions) — questions, ideas, use-case sharing
- [`docs/develop.md`](develop.md) — general developer guide (Method 1 venv with `uv`, Method 2 DevContainer, Method 3 Docker)
- [`AGENTS.md`](../AGENTS.md) — agent-side rules (read by AI tools; humans read to understand agent constraints)
- Maintainer scope corridors: [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) (Layers 1-3, zero-config default), [Discussion #789](https://github.com/davidusb-geek/emhass/discussions/789) (EMHASS = MILP core, glue layer separate)
- Issue templates: `.github/ISSUE_TEMPLATE/`

---

Cross-references: [`docs/develop.md`](develop.md), [`AGENTS.md`](../AGENTS.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md).

AI-tool-coverage gaps: Cursor (§1b) and Aider (§1c) are untested stubs. PRs adding tested-against patterns welcome.
````

- [ ] **Step 6.2: Word count check (final body)**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: in `[1300, 1700]` per spec D6.

If count is out of range:
- Under 1300: expand the thinnest section (likely §1b/c stubs or §4 checklist with 1-line whys per item).
- Over 1700: trim §3 landmine prose (each landmine should be ~55 words).

- [ ] **Step 6.3: Commit**

```bash
git add docs/develop_ai_coders.md
git commit -m "docs(ai-coders): add Section 5 red-flags + Section 6 help + footer"
```

---

## Task 7: Cross-link edits

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `AGENTS.md`
- Modify: `docs/index.md` OR `docs/section_reference.md` (per Task 1.9 finding)

- [ ] **Step 7.1: Edit `CONTRIBUTING.md`**

Find the existing line:
```
For AI coding agents working on EMHASS source, see [`AGENTS.md`](AGENTS.md).
```

Add a new line immediately below it:
```
Driving an AI coding agent on this codebase? See [`docs/develop_ai_coders.md`](docs/develop_ai_coders.md) for human-side guidance.
```

- [ ] **Step 7.2: Verify CONTRIBUTING.md edit**

```bash
grep -n "develop_ai_coders" CONTRIBUTING.md
```
Expected: 1 match.

- [ ] **Step 7.3: Edit `AGENTS.md` preamble**

Find the description block at the top (after the YAML frontmatter and the `<!-- Last verified ... -->` comment, before the `## Repository layout` heading). Insert a new italics-line right before `## Repository layout`:

```
*Humans driving an agent on this codebase: see [`docs/develop_ai_coders.md`](docs/develop_ai_coders.md) for the contributor-side companion to this file.*
```

- [ ] **Step 7.4: Verify AGENTS.md edit**

```bash
grep -n "develop_ai_coders" AGENTS.md
```
Expected: 1 match, in the preamble (line < 15).

- [ ] **Step 7.5: Edit Sphinx toctree**

Per Task 1.9, the file owning the `develop` toctree entry is either `docs/index.md` or `docs/section_reference.md`. Open the file Task 1.9 identified and locate the toctree containing `develop`. Insert `develop_ai_coders` immediately after `develop`:

Example transformation (in whichever file owns the toctree):
```
```{toctree}
:maxdepth: 2
develop
develop_ai_coders
```
```

(Indentation must match the surrounding toctree lines exactly.)

- [ ] **Step 7.6: Verify toctree edit**

```bash
grep -rn "develop_ai_coders" docs/*.md
```
Expected: 2 matches — one in the cross-reference block of `develop_ai_coders.md` itself (the cross-link text), one in the toctree.

- [ ] **Step 7.7: Commit all three cross-link edits as one commit**

```bash
git add CONTRIBUTING.md AGENTS.md docs/*.md
git commit -m "docs(ai-coders): wire cross-links from CONTRIBUTING.md + AGENTS.md + toctree"
```

---

## Task 8: Length + privacy lint

**Files:** read-only

- [ ] **Step 8.1: Final length check**

```bash
wc -w docs/develop_ai_coders.md
```
Expected: in `[1300, 1700]`.

- [ ] **Step 8.2: Privacy lint (cookbook baseline + AG-onboarding extension)**

```bash
grep -riE "loxone|loxonesmarthome|192\.168|10\.0\.|172\.(1[6-9]|2[0-9]|3[01])\.|\.lan\b|\.local\b|U:/|U:\\\\|/nodered/|Ottenhofen|SOLCAST_API_KEY|INFLUXDB_TOKEN|ce3wd000tab|f235d8fbcc04334a|882f627fbb0afc5f|6\.96 ?kWp|48\.21|11\.87|V[0-9]+\.[0-9]+|Audit \+ API|thermal/deferrable" docs/develop_ai_coders.md CONTRIBUTING.md AGENTS.md
```
Expected: zero matches.

- [ ] **Step 8.3: Private-board-ID lint (AG-onboarding-specific per spec D11)**

```bash
grep -nE '\b(U|AC|AG|EV|AM|CE|AC-[0-9]+[a-z]?|U-[0-9]+|EV-[0-9]+|AG-[0-9]+|AG-[a-z]+|AM-[0-9]+|CE-[0-9]+|DOC-[a-z]+)\b' docs/develop_ai_coders.md
```
Expected: zero matches OR only inside code-block contexts where they reference upstream PR-issue-numbers (e.g. `#828` is fine, `AC-2a` would be a leak). Manually eyeball any matches.

If a private board-ID slipped in: redact (replace with the equivalent real PR-issue-number or remove the example).

- [ ] **Step 8.4: Sphinx build check (if available locally)**

```bash
cd docs && ./make.bat html 2>&1 | tail -30
cd ..
```

Or:
```bash
sphinx-build -b html docs docs/_build/html 2>&1 | tail -30
```

Expected: build succeeds. Warnings naming `develop_ai_coders.md` are NOT acceptable. If sphinx-build is not installed locally: skip this step and rely on RTD preview / upstream CI.

- [ ] **Step 8.5: Manual render check (optional, if Sphinx built)**

Open `docs/_build/html/develop_ai_coders.html`. Verify:
- All 6 section headings render
- ASCII-tree renders in monospace block
- Real PR-ref links are clickable
- Internal cross-refs resolve
- Cross-link in CONTRIBUTING.md renders to the right page
- Cross-link in AGENTS.md renders to the right page
- Toctree-entry shows in navigation alongside `develop`

- [ ] **Step 8.6: No commit**

---

## Task 9: Push branch + open PR

- [ ] **Step 9.1: Push**

```bash
git push -u origin docs/ag-onboarding
```

- [ ] **Step 9.2: Open PR**

Title:
```
docs: add develop_ai_coders.md AI-coder contributor onboarding
```

Body: use the verbatim block from the `## Handoff-Prompt` section at the bottom of this plan.

Windows pwsh:
```powershell
$body = @'
<paste body from Handoff-Prompt section verbatim>
'@
$bodyFile = New-TemporaryFile
Set-Content -Path $bodyFile -Value $body -Encoding UTF8
gh pr create `
  --repo davidusb-geek/emhass `
  --base master `
  --head OptimalNothing90:docs/ag-onboarding `
  --title "docs: add develop_ai_coders.md AI-coder contributor onboarding" `
  --body-file $bodyFile
Remove-Item $bodyFile
```

Expected: PR URL printed.

- [ ] **Step 9.3: Capture URL**

```bash
gh pr view --json url -q .url
```

---

## Task 10: Report HANDOFF-RESULT

- [ ] **Step 10.1: Compose result block**

Paste back into orchestrator session:

```
HANDOFF-RESULT AG-onboarding
status: pr-open
pr-url: <URL from Task 9.3>
branch: docs/ag-onboarding
tests: length-lint pass (1300-1700 range); privacy-lint zero matches; private-board-ID lint clean; sphinx build pass (or skipped if not available locally)
notes: 7 commits (Intro+S1 / S2 / S3+citations / S4 / S5+S6+footer / cross-links / privacy-lint); 7 landmines source-cited; 5 real upstream PR-refs in decision-tree; caveman-full style applied with multi-step-sequence exceptions per spec D8; PR body flags style-risk per spec D9
```

---

## Self-review checklist (mentally before declaring done)

- [ ] Spec D1 target file `docs/develop_ai_coders.md` exists with all 6 sections + Intro + Footer? (Tasks 2-6)
- [ ] Spec D2 ASCII-tree in fenced block, no mermaid? (Task 3)
- [ ] Spec D3 Cursor + Aider marked "untested — contribution welcome"? (Task 2)
- [ ] Spec D4 5+ real upstream PR-refs (#817, #814, #835, #836, #831, #830) in decision-tree? (Task 3)
- [ ] Spec D5 cross-links in CONTRIBUTING.md + AGENTS.md preamble + toctree? (Task 7)
- [ ] Spec D6 length in `[1300, 1700]`? (Task 8.1)
- [ ] Spec D7 section-budgets approximately match (no section bloated or starved)?
- [ ] Spec D8 caveman-full style applied to artifact, multi-step-sequence exceptions honored?
- [ ] Spec D10 no `repomix` mention anywhere?
- [ ] Spec D11 privacy lint passes including private-board-ID extension? (Task 8.2 / 8.3)
- [ ] Spec D12 soft-dep placeholders use the right wording ("TBD when AG-B1 ships", "TBD when AM-5 lands")?
- [ ] Spec D13 each landmine in §3 has a `file:line` OR `PR-ref` citation? (Task 4)
- [ ] Spec D14 no new `docs/contributing/` subfolder?
- [ ] Branch name exactly `docs/ag-onboarding`?
- [ ] PR title conventional commit `docs: ...`?

If any flips to No: STOP, append `## Pivot Reason`, hand back via `HANDOFF-RESULT status: blocked`.

## Handoff-Prompt

**Copy-paste into a NEW Claude Code session opened in `C:/Users/MauricioSchäpers/claude-code/emhass/` (the fork):**

````
You are a fork-session for emhass upstream PR work. The main planning session lives in
`C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`. You operate ONLY here in
the `emhass` fork repo.

## Item context
- Board ID: AG-onboarding
- Corridor: https://github.com/davidusb-geek/emhass/discussions/808 (Layer-1 AI-coder docs)
- Hard-dep PR (merged 2026-04-30): https://github.com/davidusb-geek/emhass/pull/831 (AGENTS.md introduction)
- Goal-fit: (empty — non-goal hygiene, corridor-blessed)
- Spec: docs/superpowers/specs/2026-05-11-ag-onboarding-design.md
- Plan: docs/superpowers/plans/2026-05-11-ag-onboarding.md

Spec + plan in sibling repo. Read via:
  cat ../emhass-contributions/docs/superpowers/specs/2026-05-11-ag-onboarding-design.md
  cat ../emhass-contributions/docs/superpowers/plans/2026-05-11-ag-onboarding.md

## Pre-flight (mandatory)
1. gh auth status — OptimalNothing90 active.
2. git fetch upstream && git checkout master && git merge --ff-only upstream/master
3. git checkout -b docs/ag-onboarding (exact name, do not invent)
4. git status — empty.

## Implementation
Use superpowers:executing-plans. Plan path:
  ../emhass-contributions/docs/superpowers/plans/2026-05-11-ag-onboarding.md
Follow Tasks 1-10 step-by-step.

CRITICAL — Task 1 source-trace MUST succeed before any doc-content edits. Verify AGENTS.md + CONTRIBUTING.md exist, SOC ×100 line citable, dual-logger evidence, OptimizationCacheKey location, PR #785 still about thermal-battery, 6 example PRs all valid. Halt-on-drift per Step 1.10.

CRITICAL — Caveman-full style applied to the artifact (Spec D8). Multi-step instructions use normal grammar for clarity (Auto-Clarity exception). Code blocks unchanged. Checklists / bullets / tables caveman OK.

CRITICAL — Privacy: NO private board-IDs in the doc (Spec D11). Use real upstream PR/issue numbers only. Examples: #817 / #814 / #831 / #835 / #836 / #830 / #785 / #828 / #808 / #789 / #823 / #824 are all OK (public). U-1 / AC-2a / AG-7 / AG-B1 / AM-5 / DOC-cookbook etc. would be PRIVATE-LEAK.

## PR creation
After all plan tasks complete + verification passes:

  git push -u origin docs/ag-onboarding

Title: docs: add develop_ai_coders.md AI-coder contributor onboarding

PR body — write this block to a temp file then `gh pr create --body-file <file>`:

## Summary
Adds `docs/develop_ai_coders.md` — a ~1500-word human-facing companion to `AGENTS.md` (introduced in PR #831). Where `AGENTS.md` carries vendor-neutral rules for the agent and `docs/develop.md` is the general developer guide, this new doc instructs the **human driving the AI agent** with EMHASS-specific concerns: seven landmines AI tools won't flag (sign conventions, SOC scaling, MILP infeasibility, q_input_start=0, dual logger, OptimizationCacheKey, source-resolve discipline), decision-tree for issue-first vs PR-direct with real upstream PR examples, pre-PR self-check, red-flags meaning stop-and-ask, help-resources.

Layer-1 deliverable for [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) corridor (AI-coder-friendly docs).

## Why
AI-coder contributors run into recurring EMHASS landmines that the agent itself does not flag. PRs land with sign-convention guesses, SOC-scaling mistakes, infeasibility-relaxation patches, missing OptimizationCacheKey updates — each costing reviewer time and round-trips. `AGENTS.md` constrains the agent; this doc trains the human in front of the agent to recognise the landmines, scope the PR, and stop-and-ask in the right cases.

## What is in this PR
- New `docs/develop_ai_coders.md` (~1500 words across 6 sections + intro + footer)
- `CONTRIBUTING.md` +1 line cross-link
- `AGENTS.md` preamble +1 italics-line cross-link
- Sphinx toctree entry alongside `develop`

## Real-PR teaching examples used in §2 decision-tree
- PR-direct: #817 (regression_model typo), #814 (broken doc link)
- Issue-first: #835 filed issue #828 first
- Discussion-first variant: #836 (Discussion #824), #831 (Discussion #808)
- Cautionary: #830 (no issue first → review round-trip on direction)

## Style note (heads-up for review)
The doc is written in **caveman-full / dense-rule-doc** style — terse, fragments OK in lists, no filler — matching the tone AGENTS.md established. Multi-step instructions use normal grammar for clarity (Auto-Clarity exception). If this style misses the maintainer's intent for a contributor-facing onboarding doc, happy to pivot to concise-professional on this branch in a review-feedback patch commit. Style-risk-flag explicit so it can be voted on pre-merge.

## Test plan
- Word count in `[1300, 1700]` (lint script in plan Task 8.1)
- Privacy lint zero matches (baseline + private-board-ID extension)
- Sphinx build clean — no warnings naming the new file
- All 5 example PR-refs in §2 click through to merged or open PRs

## Notes
- Hard-dep: AGENTS.md introduction (PR #831, merged 2026-04-30).
- Soft-dep placeholders: ruff IS enforced today (per AGENTS.md L26); pre-commit-local-enforcement = "TBD when AM-5 lands"; public skill plugin = "TBD when AG-B1 ships". These are explicit in the doc body.
- No new Sphinx dependency, no new tooling, no new subfolder.
- AC-5 llms-full.txt will auto-pickup via Sphinx toctree — no manual coordination needed.

## Return contract — required output back to main session
Send a single message in this format:

HANDOFF-RESULT AG-onboarding
status: pr-open | blocked | failed
pr-url: <url-or-none>
branch: docs/ag-onboarding
tests: pass | fail | skipped
notes: <one-line summary or pivot reason>

## Pivot trigger
If during implementation you discover the plan does not match upstream reality (AGENTS.md missing, citations drift, example PRs returning 404, toctree owner-file different):
1. Do NOT improvise.
2. Do NOT push partial work.
3. Append `## Pivot Reason` to
   ../emhass-contributions/docs/superpowers/plans/2026-05-11-ag-onboarding.md
4. Set status: blocked, return.

## Out of scope (this session)
- Spec edits — main session
- Board mutations — main session
- repomix tool or repomix.config.json — explicitly skipped per spec D10
- New docs/contributing/ subfolder — explicitly skipped per spec D14
- AGENTS.md content-changes beyond the 1-line preamble cross-link
- Cursor / Aider tooling QA — author cannot authentic-test

## Session resumability
DO NOT close this session after HANDOFF-RESULT. Re-routes (style-feedback from maintainer, citation drift discovered, sourcery-bot review) resume here via `claude --resume`, never a fresh session.
````

After Fork-Session reports HANDOFF-RESULT, return to main session and paste the result.
Main session will:
- On pr-open: update Board-Card to Status: Review, add PR sibling card
- On blocked: read appended Pivot Reason, re-plan (resume same fork session)
- On failed: triage, decide
