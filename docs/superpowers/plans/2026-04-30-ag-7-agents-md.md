# AG-7 — Add `AGENTS.md` to upstream EMHASS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `AGENTS.md` (vendor-neutral rules for AI coding agents) at the root of `davidusb-geek/emhass`, plus a one-line discoverability pointer in `CONTRIBUTING.md`.

**Architecture:** Documentation-only PR. Source of truth for content is the AG-7 spec (`docs/superpowers/specs/2026-04-30-ag-7-agents-md-design.md`). Plan executes in the dedicated worktree at `C:/Users/MauricioSchäpers/claude-code/emhass-ag7/` on branch `docs/agents-md` (already created from `upstream/master`). Each section commits separately for granular review history. After draft is complete, the spec commits are moved off the implementation branch to a parallel `planning/ag-7` branch so the upstream PR diff contains only the two file changes.

**Tech Stack:** Markdown + YAML frontmatter, plain shell utilities (`grep`, `wc`, `git`), `gh` CLI, the `humanizer` skill.

---

## File Structure

| Path | Responsibility | New / Modified |
|---|---|---|
| `AGENTS.md` (repo root) | Vendor-neutral AI-agent rules document. Frontmatter + freshness marker + repository-layout preamble + 7 sections per spec. | New |
| `CONTRIBUTING.md` (repo root) | One-line addition pointing AI agents at `AGENTS.md`. Existing 4-line stub otherwise unchanged. | Modified |
| `docs/superpowers/specs/2026-04-30-ag-7-agents-md-design.md` | Internal spec — moves to `planning/ag-7` branch before push. | Branch-only |
| `docs/superpowers/plans/2026-04-30-ag-7-agents-md.md` | This plan — moves to `planning/ag-7` branch before push. | Branch-only |

The two `docs/superpowers/...` files exist on `docs/agents-md` for traceability during implementation but **must not** appear in the upstream PR diff. Task 15 enforces this.

---

## Task 1: Pre-flight reconnaissance

**Goal:** Gather every fact the file content depends on. No commit. No file changes. Outputs feed Tasks 2–9.

**Files:** none (read-only).

- [ ] **Step 1: Confirm worktree state**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-ag7
git status
git log --oneline -5
```

Expected: clean working tree; `HEAD` at `d1f0044` (best-practice integration commit) on branch `docs/agents-md`.

- [ ] **Step 2: Capture freshness-marker SHA + date**

```bash
git rev-parse --short=7 upstream/master
date +%Y-%m-%d
```

Record both outputs. They go into the freshness marker in Task 2 Step 3.

- [ ] **Step 3: Verify Section 2 stage-map symbols against `upstream/master`**

For each pipeline stage, locate the actual function name in upstream code:

```bash
git --no-pager grep -nE "^def (set_input_data|forecast_model_fit|forecast_load_fit|publish_data)" upstream/master -- src/emhass/command_line.py
git --no-pager grep -nE "^    def (build_lp|solve)" upstream/master -- src/emhass/optimization.py
```

Record actual function names. If a function does not exist by that name, search broadly:

```bash
git --no-pager grep -nE "^def [a-z_]*input" upstream/master -- src/emhass/command_line.py
git --no-pager grep -nE "^def [a-z_]*forecast" upstream/master -- src/emhass/command_line.py
git --no-pager grep -nE "^def [a-z_]*publish" upstream/master -- src/emhass/command_line.py
git --no-pager grep -nE "^    def [a-z_]*lp" upstream/master -- src/emhass/optimization.py
git --no-pager grep -nE "^    def [a-z_]*solve" upstream/master -- src/emhass/optimization.py
```

Output format for the implementer's notebook:

```
input_data       → command_line.py::<actual_name>
pv_forecast      → command_line.py::<actual_name>
load_forecast    → command_line.py::<actual_name>
lp_build         → optimization.py::<actual_name>
solve            → optimization.py::<actual_name>
publish          → command_line.py::<actual_name>
```

These six pairs go into Section 2 verbatim in Task 4.

- [ ] **Step 4: Verify Section 3 don't-touch claims**

```bash
git --no-pager grep -n 'split(" ", 1)\[0\] == "ERROR"' upstream/master -- src/emhass/web_server.py
git --no-pager grep -nE "^def get_logger" upstream/master -- src/emhass/utils.py
git --no-pager grep -nE "if not [a-zA-Z_]*\.handlers" upstream/master -- src/emhass/utils.py
git --no-pager grep -n "app\.logger" upstream/master -- src/emhass/web_server.py
```

Each command should produce at least one match. Record exact line content for any match. If any command returns empty, flag for the user before proceeding — Section 3 may need rewording.

- [ ] **Step 5: Verify referenced docs and links**

```bash
test -f upstream/docs/develop.md && echo OK || echo MISSING
git --no-pager grep -nE "^#+ .*[Aa]dding a parameter" upstream/master -- docs/develop.md
test -f upstream/docs/study_cases/index.md && echo OK || echo MISSING
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/davidusb-geek/emhass/issues/789
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/davidusb-geek/emhass/discussions/808
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/users/davidusb-geek/projects/2
curl -sI -o /dev/null -w "%{http_code}\n" https://emhass.readthedocs.io/en/latest/llms.txt
curl -sI -o /dev/null -w "%{http_code}\n" https://diataxis.fr/
```

Note: `upstream/docs/develop.md` checks against the upstream submodule path used in this worktree's tree; if not present in this worktree, run `git --no-pager show upstream/master:docs/develop.md | head -1` instead.

Expected: every HTTP status `200`. Every file path present.

- [ ] **Step 6: Verify line-count baseline of upstream `CONTRIBUTING.md`**

```bash
git --no-pager show upstream/master:CONTRIBUTING.md | wc -l
git --no-pager show upstream/master:CONTRIBUTING.md
```

Expected: 4 lines. If different, the spec's "currently a 4-line stub" claim is stale — proceed but note for the PR body.

- [ ] **Step 7: Record the AG-7 board body source for prose drafting**

```bash
cd ../emhass-contributions
python -c "import sys, io, json; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8'); d = json.load(open('board/items.json', encoding='utf-8')); items = d if isinstance(d, list) else d.get('items', d); [print(i.get('body','')) for i in items if i.get('id')=='AG-7']" > /tmp/ag7-body-source.txt
wc -l /tmp/ag7-body-source.txt
cd ../emhass-ag7
```

This raw body is the prose starting point. Do not copy verbatim — the editorial pass in Tasks 10–12 strips internals and humanizes. The board body holds the structure and concrete examples to preserve.

No commit at the end of Task 1 — outputs are working notes for subsequent tasks.

---

## Task 2: AGENTS.md skeleton — frontmatter, freshness marker, repository layout, section headers

**Files:**
- Create: `AGENTS.md` (repo root of worktree)

- [ ] **Step 1: Write a length-cap test**

```bash
test_length_cap() {
  lines=$(wc -l < AGENTS.md)
  if [ "$lines" -gt 350 ]; then
    echo "FAIL: AGENTS.md is $lines lines, cap is 350"
    return 1
  fi
  echo "OK: $lines lines (cap 350)"
}
```

Save to a scratch file `/tmp/agents-checks.sh`. Reused in later tasks.

- [ ] **Step 2: Write a frontmatter-validity test**

```bash
test_frontmatter() {
  python -c "
import yaml, sys
with open('AGENTS.md') as f:
    text = f.read()
parts = text.split('---', 2)
if len(parts) < 3:
    print('FAIL: no closing --- delimiter'); sys.exit(1)
fm = yaml.safe_load(parts[1])
assert 'name' in fm and 'description' in fm, 'FAIL: missing name/description'
print('OK:', fm)
"
}
```

Append to `/tmp/agents-checks.sh`.

- [ ] **Step 3: Run both tests against a non-existent file to confirm they fail**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-ag7
source /tmp/agents-checks.sh
test_length_cap   # expected: error, file not found
test_frontmatter  # expected: error, file not found
```

- [ ] **Step 4: Create `AGENTS.md` with skeleton content**

Substitute `<SHA-7>` and `<DATE>` from Task 1 Step 2. Section bodies are placeholders to be filled in Tasks 3–9; the section headings themselves are final.

```markdown
---
name: emhass-agents
description: Vendor-neutral rules for AI coding agents working on EMHASS source.
---

<!-- Last verified against upstream/master @ <SHA-7>, <DATE> -->

This file documents rules for AI coding agents (Claude Code, Cursor, Aider, Copilot, Codex) working on EMHASS source. It complements `docs/develop.md` (canonical for humans) and does not duplicate its content. Where `docs/develop.md` already covers a topic, this file links and adds AI-specific constraints on top.

## Repository layout

- `src/emhass/` — core module: `optimization.py`, `forecast.py`, `retrieve_hass.py`, `web_server.py`, `command_line.py`, `utils.py`.
- `tests/` — pytest suite.
- `docs/` — Sphinx source. Start with `develop.md`; worked examples in `study_cases/`.
- `data/` — config defaults and schema (`config_defaults.json`, `associations.csv`).
- `src/emhass/static/` — web UI assets, including `param_definitions.json`.

## Section 1 — Canonical commands

(filled in Task 3)

## Section 2 — Stage map

(filled in Task 4)

## Section 3 — Don't-touch rules

(filled in Task 5)

## Section 4 — Maintainer scope corridors

(filled in Task 6)

## Section 5 — Limits and gotchas

(filled in Task 7)

## Section 6 — Conventions

(filled in Task 8)

## Section 7 — Where to find more

(filled in Task 9)
```

- [ ] **Step 5: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

Expected: both `OK`.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add AGENTS.md skeleton (frontmatter, layout, section headers)"
```

---

## Task 3: Section 1 — Canonical commands + tech stack

**Files:**
- Modify: `AGENTS.md` (replace the `(filled in Task 3)` placeholder under Section 1)

- [ ] **Step 1: Draft Section 1 content**

Replace the Section 1 placeholder block with this final content. The "Tech stack" mini-table satisfies the OpenAI Codex and GitHub Copilot best-practice requirement to pin versions agents need for library-API decisions.

```markdown
## Section 1 — Canonical commands

Setup, environment variables, and the full developer workflow live in `docs/develop.md` (Method 1 Python venv with `uv`, Method 2 DevContainer, Method 3 Docker). Read that first.

Quick-recall for AI tools:

| Action | Command |
|---|---|
| Run tests | `pytest tests/` |
| Sync dev deps | `uv sync --extra test` |
| Build docs | `sphinx-build -b html docs docs/_build` (configured in `docs/conf.py`) |
| Lint | No enforced linter at the time of writing. |

Tech stack (verify versions in `pyproject.toml` before assuming an API):

| Component | Version source |
|---|---|
| Python | `pyproject.toml` `requires-python` |
| Pydantic | v1 at the time of writing |
| Optimisation | CVXPY (pin in `pyproject.toml`) |
| Web | Flask |
| Tests | pytest |
```

- [ ] **Step 2: Verify the section does not duplicate `docs/develop.md`**

```bash
git --no-pager show upstream/master:docs/develop.md | grep -iE "uv sync|pytest|sphinx-build" | head -10
```

Expected: `develop.md` mentions these commands as part of fuller setup prose. Section 1 is a quick-recall table, not setup steps. The two are complementary (the develop.md text walks setup; the AGENTS.md table is grep-friendly recall). Confirm visually.

- [ ] **Step 3: Run skeleton tests again**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

Both `OK`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 1 — canonical commands and tech stack"
```

---

## Task 4: Section 2 — Pipeline map

**Files:**
- Modify: `AGENTS.md` (replace Section 2 placeholder)

The original board-body assumed six standalone pipeline functions (`set_input_data`, `forecast_model_fit`, `forecast_load_fit`, `build_lp`, `solve`, `publish_data`). Reconnaissance against `upstream/master` showed those names do not all exist as standalone defs. The corrected design is a two-layer map: a public entry-point table plus a stage-label pointer to `stage_timer` instrumentation.

- [ ] **Step 1: Draft Section 2 with the verified two-layer content**

Replace the Section 2 placeholder with this exact content:

```markdown
## Section 2 — Pipeline map

EMHASS exposes three optimisation modes from `command_line.py`. All share an input-prep step and a publish step; the body differs by mode. The optimisation core is one method on the `Optimization` class.

| Phase | Symbol |
|---|---|
| Input preparation | `command_line.py::set_input_data_dict` |
| Mode entry, perfect forecast | `command_line.py::perfect_forecast_optim` |
| Mode entry, day-ahead | `command_line.py::dayahead_forecast_optim` |
| Mode entry, rolling MPC | `command_line.py::naive_mpc_optim` |
| Optimisation core (LP build and CVXPY solve) | `optimization.py::Optimization.perform_optimization` |
| Publish | `command_line.py::publish_data` |

For finer-grained stage instrumentation, the codebase uses `stage_timer(stage_times, "<label>", logger)` blocks. Five labels are in active use:

- `"pv_forecast"`
- `"load_forecast"`
- `"price_prep"`
- `"optim_solve"`
- `"publish"`

Grep `'stage_timer.*"<label>"'` for the live call site at any time. The labels are stable across refactors; the line numbers are not.
```

- [ ] **Step 2: Verify each entry-point symbol exists in upstream**

```bash
for sym in set_input_data_dict perfect_forecast_optim dayahead_forecast_optim naive_mpc_optim publish_data; do
  count=$(git --no-pager grep -cE "^async def $sym\b" upstream/master -- src/emhass/command_line.py)
  echo "$sym: $count"
done
git --no-pager grep -cE "^    def perform_optimization\b" upstream/master -- src/emhass/optimization.py
```

Expected: each `command_line.py` symbol shows `1`. The `optimization.py` line shows `1`. If any zero, the upstream code drifted — re-run reconnaissance and update Step 1.

- [ ] **Step 3: Verify each stage_timer label is present**

```bash
for label in pv_forecast load_forecast price_prep optim_solve publish; do
  count=$(git --no-pager grep -cE "stage_timer\(.*\"$label\"" upstream/master -- src/emhass/command_line.py)
  echo "$label: $count"
done
```

Expected: every label shows a count `>= 1`. If any zero, drop that label from the bullet list and continue.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 2 — pipeline map (entry points + stage labels)"
```

---

## Task 5: Section 3 — Don't-touch rules

**Files:**
- Modify: `AGENTS.md` (replace Section 3 placeholder)

- [ ] **Step 1: Draft Section 3**

```markdown
## Section 3 — Don't-touch rules

These four invariants are easy to break by accident and hard to detect in CI.

1. **`action_logs.txt` line format.** The web server's error-detection logic in `src/emhass/web_server.py` parses each line by splitting on the first whitespace and comparing the leading token to `"ERROR"`. Any change to the log line format (extra prefix, structured-logging migration, JSON envelope) silently breaks error reporting in the UI.

2. **Logger handler accumulation in `utils.get_logger`.** The function attaches a handler unconditionally on every call. Calling it twice for the same logger name produces duplicated log lines, which has historically masked real failures by hiding them in scroll-back. Avoid duplicate calls; if a guard becomes appropriate, coordinate the change with the maintainer because both the CLI and the web path call into this function.

3. **Two parallel logging subsystems.** The CLI path uses `utils.get_logger`. The web path uses `app.logger` (the Flask logger). Logging changes touch both consistently or land in neither — partial migrations leave the two paths emitting different formats and break log consumers downstream.

4. **`param_definitions.json` is a structured surface.** Additive changes only. Renaming a key, removing one, or changing its type contract breaks the configuration UI and any external tooling that reads the schema. New entries are fine; mutations need a migration plan and a maintainer-led review.
```

- [ ] **Step 2: Cross-check the four claims still hold in upstream code**

```bash
git --no-pager grep -n 'split(" ", 1)\[0\] == "ERROR"' upstream/master -- src/emhass/web_server.py
git --no-pager grep -nB1 -A3 "if not [a-zA-Z_]*\.handlers" upstream/master -- src/emhass/utils.py
git --no-pager grep -n "app\.logger" upstream/master -- src/emhass/web_server.py
test -f upstream/src/emhass/static/data/param_definitions.json || git --no-pager show upstream/master:src/emhass/static/data/param_definitions.json | head -1
```

Each command must produce a result. If any returns empty, the claim does not hold and the bullet must be reworded.

- [ ] **Step 3: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 3 — don't-touch rules"
```

---

## Task 6: Section 4 — Maintainer scope corridors

**Files:**
- Modify: `AGENTS.md` (replace Section 4 placeholder)

- [ ] **Step 1: Draft Section 4**

```markdown
## Section 4 — Maintainer scope corridors

These corridors come from public maintainer statements. Cite the source if a contributor questions them.

- **Threat model** (Discussion #808): the project's security envelope is code injection, not auth bypass or data leakage. Endpoints that read in-memory state are inside the corridor; endpoints that touch the filesystem, a database, or shell out are not, and need explicit maintainer sign-off.
- **EMHASS scope** (Issue #789): EMHASS is a MILP optimiser. Vehicle APIs, OCPP, EVCC, and direct charger modulation belong in the integration layer, not in core.
- **Glue layer is agnostic.** Node-RED, MQTT, Home Assistant, and generic automations are equivalent integration paths. Do not wire Home-Assistant-specific code paths into core.
- **Zero-config default must keep working.** The add-on must continue to start and produce a sensible optimisation with default configuration after every change.
```

- [ ] **Step 2: Confirm the cited issues are still public**

```bash
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/davidusb-geek/emhass/issues/789
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/davidusb-geek/emhass/discussions/808
```

Both `200`.

- [ ] **Step 3: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 4 — maintainer scope corridors"
```

---

## Task 7: Section 5 — Limits and gotchas (heart of the document)

**Files:**
- Modify: `AGENTS.md` (replace Section 5 placeholder)

This is the section the maintainer specifically endorsed. Preserve concrete examples; do not abstract them. Length budget for this section: roughly 80–100 lines.

- [ ] **Step 1: Draft Section 5**

```markdown
## Section 5 — Limits and gotchas (read this if you are an AI coder or working with one)

AI coders find code locations and produce candidate changes. Domain experts decide whether something is a bug or design. A 2026-04-26 schema audit illustrates the split: of eight candidate findings, four were confirmed bugs and PR-able, four needed maintainer judgment and went issue-first. Skipping the human-in-the-loop step produces roughly fifty percent noise.

**File an issue, not a PR, when:**

- Behaviour changes in any visible way (output values, log format, error messages).
- A magic constant or sentinel might be intentional ("`=0` means no constraint?", "negative value treated as disabled?").
- A condition looks wrong but might encode a domain convention you do not know (AC vs DC stack power; charge vs discharge sign conventions).
- The change touches `optimization.py`, `retrieve_hass.py`, or `forecast.py` beyond about three lines.

**Always verify before claiming done:**

- Sign conventions (`P_grid > 0` means import? export? Check; do not assume).
- Units in the wild (Home Assistant scales SOC by 100; CSV uses 0..1; they differ).
- A test reproducer is present for any behaviour-change PR.
- Container or UI smoke-test (`docker compose up` plus the browser config page) if schema or `web_server.py` changed.

**Do not refactor without an issue:**

- Restructuring `optimization.py` (3000+ lines) without an architecture-RFC issue gets rejected.
- Renaming public API parameters breaks downstream consumers; needs a migration path.
- Adding new dependencies is coordinated via issue first.

**Adding a parameter:** follow the four-step workflow documented in `docs/develop.md` (`associations.csv` plus `config_defaults.json` plus `param_definitions.json` plus `OptimizationCacheKey`, optionally `check_def_loads`). Skipping any step breaks something.

**Things AI tools commonly hallucinate or get wrong here:**

- Confusing `param_definitions.json` (GUI hint metadata) with `config_defaults.json` (authoritative defaults).
- Inventing solver or CVXPY APIs that do not exist in the pinned version.
- Suggesting Pydantic v2 patterns when the codebase is still on v1 (or vice versa — verify in `pyproject.toml`).
- Forgetting that the public `command_line.py` entry points (`set_input_data_dict`, `perfect_forecast_optim`, `dayahead_forecast_optim`, `naive_mpc_optim`, `publish_data`) are `async def` and writing synchronous wrappers around them.

**Token and context limits:** the largest source files (`optimization.py`, `command_line.py`, both 3000+ lines) exceed comfortable context for many models. Use `repomix` (`npx repomix`) to flatten the repo for full-context tools that support it; otherwise scope reading to specific functions.
```

- [ ] **Step 2: Verify the four AI-failure-mode claims**

```bash
test -f upstream/src/emhass/static/data/param_definitions.json || git --no-pager show upstream/master:src/emhass/static/data/param_definitions.json | head -1
test -f upstream/src/emhass/data/config_defaults.json || git --no-pager show upstream/master:src/emhass/data/config_defaults.json | head -1
git --no-pager grep -n "cvxpy" upstream/master -- pyproject.toml
git --no-pager grep -n "pydantic" upstream/master -- pyproject.toml
git --no-pager grep -n "if not [a-zA-Z_]*\.handlers" upstream/master -- src/emhass/utils.py
```

Each must produce output.

- [ ] **Step 3: Verify the four-step "Adding a parameter" workflow exists in `develop.md`**

```bash
git --no-pager show upstream/master:docs/develop.md | grep -nE "associations\.csv|config_defaults\.json|param_definitions\.json|OptimizationCacheKey"
```

Expected: at least four matching lines, confirming `develop.md` documents the workflow we point to.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 5 — limits and gotchas"
```

---

## Task 8: Section 6 — Conventions

**Files:**
- Modify: `AGENTS.md` (replace Section 6 placeholder)

- [ ] **Step 1: Draft Section 6 — two bullets only**

The board body has a third "Account hygiene" bullet for dual-account contributors. That is contributor-personal and does not belong in upstream documentation. It is dropped, not rephrased.

```markdown
## Section 6 — Conventions

- **Documentation style:** soft Diátaxis (https://diataxis.fr/) — tutorials, how-tos, reference, explanation. Pragmatic, not strictly four-quadrant. The `docs/study_cases/` directory holds the worked example.
- **Commit messages:** prefix with type (`fix`, `docs`, `feat`, `chore`) per recent maintainer practice.
```

- [ ] **Step 2: Confirm the dropped "Account hygiene" line is absent**

```bash
grep -i "account hygiene\|gh auth switch" AGENTS.md
```

Expected: no matches.

- [ ] **Step 3: Confirm the Diátaxis link still resolves**

```bash
curl -sI -o /dev/null -w "%{http_code}\n" https://diataxis.fr/
```

Expected: `200`.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 6 — conventions"
```

---

## Task 9: Section 7 — Where to find more

**Files:**
- Modify: `AGENTS.md` (replace Section 7 placeholder)

- [ ] **Step 1: Draft Section 7**

```markdown
## Section 7 — Where to find more

- [`docs/develop.md`](docs/develop.md) — canonical EMHASS development guide (fork, venv, DevContainer, Docker, adding a parameter, PR process). Read this first.
- [`llms.txt`](https://emhass.readthedocs.io/en/latest/llms.txt) — Sphinx-generated routing manifest. The file does not exist in the source tree; it is built per Sphinx run and served from Read the Docs.
- [`docs/study_cases/`](docs/study_cases/) — Diátaxis-soft worked examples per persona.
- [Project board](https://github.com/users/davidusb-geek/projects/2) — coordination and scope corridors visible per card.
```

- [ ] **Step 2: Verify all four targets**

```bash
test -f upstream/docs/develop.md || git --no-pager show upstream/master:docs/develop.md | head -1
test -d upstream/docs/study_cases || git --no-pager show upstream/master:docs/study_cases/index.md | head -1
curl -sI -o /dev/null -w "%{http_code}\n" https://emhass.readthedocs.io/en/latest/llms.txt
curl -sI -o /dev/null -w "%{http_code}\n" https://github.com/users/davidusb-geek/projects/2
```

All file checks pass; both URLs return `200`.

- [ ] **Step 3: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): add Section 7 — where to find more"
```

---

## Task 10: Editorial pass — strip internals

**Files:**
- Modify: `AGENTS.md`

The board body the prose is loosely based on contains internal board IDs and roadmap leaks. None of these may appear in the upstream file.

- [ ] **Step 1: Scan for internal IDs and roadmap leaks**

```bash
grep -nE "AC-2a|AC-2b|AC-2-fix|AM-5|U-4|AG-onboarding|AG-7" AGENTS.md
grep -nE "when [A-Z]+-[0-9]+ lands|pending [A-Z]+-[0-9]+|track via [A-Z]+-[0-9]+" AGENTS.md
grep -niE "account hygiene|gh auth switch" AGENTS.md
```

Expected: no matches. If any appear, edit them out (replace with neutral wording or remove the sentence entirely; do not stretch sentences to absorb the deletion).

- [ ] **Step 2: Verify the AGENTS.md does not refer to itself by board-item name**

```bash
grep -nE "AG-7" AGENTS.md
```

Expected: no matches.

- [ ] **Step 3: If Step 1 or Step 2 produced any matches, fix them**

For each match, edit the file with a neutral rephrasing. Re-run Step 1 and Step 2 until both produce no output.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit (only if Step 3 made any edits)**

```bash
git add AGENTS.md
git commit -m "docs(agents): editorial pass — strip internal IDs and roadmap refs"
```

If Step 3 made no edits, skip the commit.

---

## Task 11: Editorial pass — humanizer

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Snapshot the file before the humanizer pass**

```bash
cp AGENTS.md /tmp/AGENTS.before-humanizer.md
```

- [ ] **Step 2: Invoke the humanizer skill on the file**

Use the `humanizer` skill (from the user's installed plugins). Apply it to the full content of `AGENTS.md`. The skill targets em-dash overuse, AI vocabulary (`leverage`, `robust`, `comprehensive`, `delve`, `seamless`, `streamline`), inflated symbolism, vague attribution, rule-of-three, and filler phrases.

- [ ] **Step 3: Diff the result and accept selectively**

```bash
diff /tmp/AGENTS.before-humanizer.md AGENTS.md | head -200
```

Review every change. Accept changes that improve naturalness. Reject changes that:
- Strip a concrete example (the maintainer endorsed concrete examples — do not abstract them).
- Lose a code-fence or symbol reference.
- Replace a precise verb with a generic one.

If a change must be reverted, use `git checkout -- AGENTS.md` and re-run with smaller scope, or hand-edit.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): editorial pass — humanizer"
```

---

## Task 12: Editorial pass — British spelling

**Files:**
- Modify: `AGENTS.md`

Upstream maintainer prose uses British spelling (e.g., `optimiser`, `behaviour`). The AGENTS.md must match.

- [ ] **Step 1: Scan for US-variant spellings**

```bash
grep -nE "optimiz|behavior|color|analyz|favorite|center" AGENTS.md
```

- [ ] **Step 2: Replace each US variant with the British equivalent**

For each match, use Edit:
- `optimization` → `optimisation`
- `optimizer` → `optimiser`
- `optimizing` → `optimising`
- `behavior` → `behaviour`
- `color` → `colour`
- `analyze` → `analyse`
- `analyzing` → `analysing`
- `favorite` → `favourite`
- `center` → `centre`

Watch the proper noun exception: `OptimizationCacheKey` is a code identifier — keep as-is. Same for any quoted code, file path, or external library name.

- [ ] **Step 3: Re-scan to confirm**

```bash
grep -nE "optimiz|behavior|color|analyz|favorite|center" AGENTS.md
```

Expected: only false-positive matches inside code spans like `OptimizationCacheKey`. If a non-code-span match appears, fix it.

- [ ] **Step 4: Run skeleton tests**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): editorial pass — British spelling"
```

---

## Task 13: CONTRIBUTING.md one-line addition

**Files:**
- Modify: `CONTRIBUTING.md` (worktree root)

- [ ] **Step 1: Confirm the upstream stub is unchanged from the spec assumption**

```bash
cat CONTRIBUTING.md
wc -l CONTRIBUTING.md
```

Expected: 4 lines, content matches the spec's "stub pointing to develop.html".

- [ ] **Step 2: Append the AI-agents pointer**

Use Edit. Locate the final non-blank line of the file. Insert one new line after it (with one blank line separator), final content:

```markdown
For AI coding agents working on EMHASS source, see [`AGENTS.md`](AGENTS.md).
```

The end-result file is 6 lines (4 original + 1 blank + 1 new), with no trailing whitespace.

- [ ] **Step 3: Verify the new line renders as a working link**

```bash
grep -n "AGENTS.md" CONTRIBUTING.md
```

Expected: one match.

- [ ] **Step 4: Confirm `AGENTS.md` exists at the link target**

```bash
test -f AGENTS.md && echo OK || echo MISSING
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs(contributing): point AI coding agents at AGENTS.md"
```

---

## Task 14: Pre-push verification — the eleven checks

**Files:** none (read-only verification).

This task runs every check from the spec's "Verification before push" section. If any fails, fix the underlying file and re-run before continuing to Task 15.

- [ ] **Step 1: Fill the freshness marker with current values**

```bash
sha=$(git rev-parse --short=7 upstream/master)
today=$(date +%Y-%m-%d)
sed -i "s|<SHA-7>|$sha|; s|<DATE>|$today|" AGENTS.md
grep -n "Last verified" AGENTS.md
git add AGENTS.md
git commit -m "docs(agents): fill freshness marker (sha=$sha, date=$today)"
```

- [ ] **Step 2: Re-verify symbol references**

Re-run the symbol grep from Task 4 Step 2 against the names actually present in `AGENTS.md` Section 2. All counts must be `>= 1`. If any fail, the upstream code drifted between Task 4 and now — update Section 2 with current names and amend.

- [ ] **Step 3: Re-verify all HTTP links**

```bash
grep -oE "https?://[^ )]+" AGENTS.md CONTRIBUTING.md | sort -u | while read url; do
  code=$(curl -sI -o /dev/null -w "%{http_code}" "$url")
  echo "$code $url"
done
```

Every status `200` or `30x`. Any `4xx`/`5xx` is a broken link — fix.

- [ ] **Step 4: Re-verify in-repo paths referenced by `AGENTS.md`**

```bash
for path in docs/develop.md docs/study_cases src/emhass/static/data/param_definitions.json src/emhass/data/config_defaults.json src/emhass/data/associations.csv; do
  git --no-pager show upstream/master:$path > /dev/null 2>&1 && echo "OK $path" || echo "MISS $path"
done
```

All `OK`.

- [ ] **Step 5: Doc-complementarity check**

Read both files mentally side-by-side. Confirm:
- Section 1 of `AGENTS.md` lists commands but does not describe environment-setup steps (those live in `develop.md`).
- The "Adding a parameter" entry in Section 5 links and does not restate the four steps.
- No sentence in `AGENTS.md` contradicts a sentence in `develop.md` on the same topic.

- [ ] **Step 6: Length cap and frontmatter**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

Both `OK`.

- [ ] **Step 7: British-spelling final scan**

```bash
grep -nE "optimiz|behavior|color|analyz|favorite|center" AGENTS.md
```

Only matches allowed: code identifiers in backticks (e.g. `OptimizationCacheKey`).

- [ ] **Step 8: Diff sanity from upstream/master**

```bash
git diff upstream/master..docs/agents-md --stat -- AGENTS.md CONTRIBUTING.md
git diff upstream/master..docs/agents-md --stat
```

The first command shows: `AGENTS.md` (new), `CONTRIBUTING.md` (+1 line). The second command shows the same plus the `docs/superpowers/...` files for now (those are removed in Task 15).

- [ ] **Step 9: GitHub render preview is deferred to Task 17**

The github.com render check requires the branch be pushed first. Marked here as a forward dependency on Task 17.

No commit at the end of Task 14.

---

## Task 15: Move spec and plan off the implementation branch

**Files:**
- Branch: `planning/ag-7` (new)
- Branch: `docs/agents-md` (rewritten history via rebase)

The upstream PR diff must contain only `AGENTS.md` and `CONTRIBUTING.md`. The spec and plan are internal artefacts and live on a parallel `planning/ag-7` branch.

- [ ] **Step 1: Locate the last commit that introduced a `docs/superpowers/` file**

```bash
last_planning_sha=$(git log --format=%H --diff-filter=A -- docs/superpowers/ | head -1)
echo "Last planning commit: $last_planning_sha"
git --no-pager show --stat $last_planning_sha
```

Expected: SHA points at either the last spec-edit commit (`d1f0044` if no further spec edits) or the plan-commit. The diff-stat shows only `docs/superpowers/...` files.

- [ ] **Step 2: Confirm there are no commits that touch BOTH planning files AND implementation files**

```bash
git log --format='%H %s' upstream/master..docs/agents-md | while read sha rest; do
  has_planning=$(git --no-pager show --name-only --format='' $sha | grep -c "^docs/superpowers/" || true)
  has_impl=$(git --no-pager show --name-only --format='' $sha | grep -cE "^(AGENTS\.md|CONTRIBUTING\.md)$" || true)
  if [ "$has_planning" -gt 0 ] && [ "$has_impl" -gt 0 ]; then
    echo "MIXED: $sha $rest"
  fi
done
```

Expected: no output. If any commit appears here, it must be split before continuing — abort and split it manually with `git rebase -i` (out of scope for this plan; flag to the user).

- [ ] **Step 3: Create the `planning/ag-7` branch preserving spec + plan history**

```bash
git branch planning/ag-7 docs/agents-md
git log planning/ag-7 --oneline | head -20
```

`planning/ag-7` is now a peer branch at the same HEAD as `docs/agents-md`. The spec + plan history is preserved there.

- [ ] **Step 4: Rebase `docs/agents-md` onto `upstream/master`, dropping the planning commits**

```bash
git checkout docs/agents-md
git rebase --onto upstream/master $last_planning_sha docs/agents-md
```

`git rebase --onto NEW UPSTREAM BRANCH` replays everything after `UPSTREAM` on `BRANCH` onto `NEW`. Here: replay every commit AFTER `$last_planning_sha` (the last planning commit) onto `upstream/master`. The planning commits themselves are dropped because they sit at or before `$last_planning_sha`.

- [ ] **Step 5: Verify the final diff contains only the two files**

```bash
git diff upstream/master..docs/agents-md --name-only
git diff upstream/master..docs/agents-md --stat
```

Expected output of the first command, exactly:

```
AGENTS.md
CONTRIBUTING.md
```

If anything else appears, the rebase included a mixed commit — return to Step 2 and split it.

- [ ] **Step 6: Sanity-run the skeleton tests on the rewritten branch**

```bash
source /tmp/agents-checks.sh
test_length_cap
test_frontmatter
```

Both `OK`.

- [ ] **Step 7: Confirm `planning/ag-7` still holds spec + plan**

```bash
git log planning/ag-7 --oneline | head -10
git --no-pager show planning/ag-7:docs/superpowers/specs/2026-04-30-ag-7-agents-md-design.md | head -5
git --no-pager show planning/ag-7:docs/superpowers/plans/2026-04-30-ag-7-agents-md.md | head -5
```

Both `head -5` outputs show valid file headers, no error.

No commit at the end of Task 15. The history rewrite is the rebase itself.

---

## Task 16: Switch GitHub account, push branch, open draft PR

**Files:** none locally.

- [ ] **Step 1: Switch the active gh account to `OptimalNothing90`**

```bash
gh auth switch --user OptimalNothing90
gh auth status
```

`gh auth status` shows `OptimalNothing90` as the active account. If it shows `mschaepers`, repeat the switch.

- [ ] **Step 2: Push the branch**

```bash
git push -u origin docs/agents-md
```

- [ ] **Step 3: Push the planning branch (private fork only — not for PR)**

```bash
git push -u origin planning/ag-7
```

This preserves the spec and plan history on the fork remote without exposing them in the PR.

- [ ] **Step 4: Open the PR as a draft**

```bash
gh pr create \
  --repo davidusb-geek/emhass \
  --base master \
  --head OptimalNothing90:docs/agents-md \
  --draft \
  --title "docs: add AGENTS.md (vendor-neutral rules for AI coding agents)" \
  --body "$(cat <<'EOF'
## Rationale

Upstream EMHASS has no vendor-neutral rules file for AI coding agents. Without one, AI tools default to inferred conventions; a 2026-04-26 schema audit illustrates the cost (8 candidate findings → 4 PR-able, 4 needed maintainer judgment). `docs/develop.md` is canonical for humans; `AGENTS.md` fills the orthogonal AI-rules gap and routes back to `develop.md` rather than restating it.

This PR adds:

- `AGENTS.md` at the repo root — frontmatter + freshness marker + repository-layout preamble + seven sections.
- `CONTRIBUTING.md` — one-line discoverability addition pointing AI agents at `AGENTS.md`.

## Maintainer ack

Per Discussion #808 reply (2026-04-27): *"rich in concrete examples, that was what was needed"* — the workflow-demo gate cleared this deliverable.

## Doc complementarity

`AGENTS.md` does **not** duplicate `docs/develop.md`. Where `develop.md` already covers a topic (setup, fork workflow, the 4-step "Adding a parameter" workflow), `AGENTS.md` links and adds AI-specific rules on top.

## Best-practice sources consulted

- [GitHub Blog — *How to write a great AGENTS.md* (2500-repo Copilot analysis)](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- [OpenAI Codex — *Best practices*](https://developers.openai.com/codex/learn/best-practices)

Adopted: minimal YAML frontmatter, freshness marker, repository-layout preamble, tech-stack with versions, length cap (350 LOC), British-spelling consistency.

Skipped (with reasons in the internal spec): three-tier Always/Ask/Never restructure (preserves the structure the maintainer ack-ed), `.github/agents/` per-tool fan-out (Copilot-specific, conflicts with universal-AGENTS.md convention), positive code-style snippets (would duplicate `develop.md`).

## Pre-push verification

- [x] Symbol references in Section 2 verified against `upstream/master`.
- [x] All HTTP links return 200.
- [x] All in-repo paths (`docs/develop.md`, `docs/study_cases/`, schema files) exist.
- [x] No duplication with `docs/develop.md`.
- [x] Humanizer pass applied; concrete examples preserved.
- [x] British spelling holds; only code identifiers carry US variants.
- [x] YAML frontmatter parses.
- [x] Freshness marker filled with actual SHA and date.
- [x] Diff contains exactly `AGENTS.md` (new) + `CONTRIBUTING.md` (+1 line).
- [x] Length under 350 LOC.
- [ ] GitHub render preview verified before marking ready.

EOF
)"
```

Capture the PR URL from the command output. Call it `<pr_url>`.

- [ ] **Step 5: Verify the PR exists and is draft**

```bash
gh pr view <pr_url> --json isDraft,state,title,baseRefName,headRefName
```

Expected JSON shows `"isDraft": true`, `"state": "OPEN"`, the correct title, base `master`, head `docs/agents-md`.

No commit at the end of Task 16.

---

## Task 17: GitHub render preview

**Files:** none.

- [ ] **Step 1: Open the PR's `AGENTS.md` rendered view**

```bash
gh pr view <pr_url> --web
```

Navigate from the PR to the file diff view (`Files changed` tab) and click on `AGENTS.md` to see GitHub's rendered preview of the file content.

- [ ] **Step 2: Visual checklist on the rendered page**

For each item, confirm visually:
- The YAML frontmatter renders as a small two-row table (or as plain `---` block; either is acceptable). It does not display as a broken `<hr>` or as raw text.
- The freshness-marker HTML comment is invisible (correct) or rendered as plain text (acceptable, but log it).
- The two tables in Section 1 (commands and tech stack) render as Markdown tables with proper column alignment.
- The Section 2 stage-map table renders correctly.
- All inline code-fences (`` ` ``) display as monospace.
- All inline links work; click each at least once.
- No emoji, no spurious Unicode, no rendered HTML beyond the deliberate comment.

- [ ] **Step 3: Open `CONTRIBUTING.md` rendered view**

Same tab, click `CONTRIBUTING.md`. Confirm the new line at the bottom renders correctly with the AGENTS.md link active.

- [ ] **Step 4: If any rendering issue is found, fix locally**

Edit the file, re-run the skeleton tests, commit with message `docs(agents): fix github render — <what>`, push, refresh the PR view.

- [ ] **Step 5: Confirm the PR diff still contains only the two files**

```bash
gh pr diff <pr_url> --stat
```

Expected: `AGENTS.md` and `CONTRIBUTING.md` only.

No commit unless Step 4 fired.

---

## Task 18: Mark PR ready and switch account back

**Files:** none.

- [ ] **Step 1: Mark the PR ready for review**

```bash
gh pr ready <pr_url>
gh pr view <pr_url> --json isDraft,state
```

Expected: `"isDraft": false`, `"state": "OPEN"`.

- [ ] **Step 2: Optional — post a follow-up note on Discussion #808**

This step is the user's discretion. Default is to skip — the maintainer receives a PR notification automatically. If the user wants the contextual link, run:

```bash
gh api repos/davidusb-geek/emhass/discussions/808/comments \
  -f body="Opened the AGENTS.md PR per your reply: <pr_url>"
```

If the user does not want this step, do nothing.

- [ ] **Step 3: Switch the gh account back to `mschaepers`**

```bash
gh auth switch --user mschaepers
gh auth status
```

`gh auth status` shows `mschaepers` as the active account.

- [ ] **Step 4: Final-state checklist**

Confirm in this exact order:
- The PR `<pr_url>` is open, ready for review, on `davidusb-geek/emhass`.
- `gh auth status` returns `mschaepers`.
- `git -C C:/Users/MauricioSchäpers/claude-code/emhass-ag7 status` is clean.
- `git -C C:/Users/MauricioSchäpers/claude-code/emhass branch --show-current` is unchanged from before this work started (still on `fix/issue-818-ignore-pv-feedback-wiring`).

- [ ] **Step 5: Update the AG-7 board entry status**

```bash
cd ../emhass-contributions
# Open board/items.json or use the helper script and move AG-7 from "Candidates" to "In Progress" → "In Review".
# Note the PR URL in the AG-7 entry.
cd ../emhass-ag7
```

The exact mechanism depends on `board/update.py` — follow the contributions repo's `AGENTS.md`.

No commit on `docs/agents-md` after the PR is open. Any post-review changes happen via new commits + `git push`.

---

## Pacing follow-up (outside this plan's scope)

After the PR is open, observe the maintainer's response before starting AC-5 or AG-onboarding. Spec records the signal-to-action mapping:

- Merge with no comment, or with positive comment → start AC-5 plan.
- Merge with reservations or scope pushback → pause, re-brainstorm with the new constraints.
- No response within roughly two weeks → ping politely once on the PR, then wait.

This plan does not schedule any of those follow-ups. Open them as new plans when the relevant signal arrives.
