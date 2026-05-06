# AG-7 — Add `AGENTS.md` to upstream EMHASS

**Date:** 2026-04-30
**Board item:** AG-7 (Phase 1.5, Priority P1, Effort M, Scope: Upstream)
**Maintainer ack:** @davidusb-geek, [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) reply 2026-04-27 — *"rich in concrete examples, that was what was needed"* (Workflow-Demo gate cleared).
**Companion docs:** `docs/develop.md` (canonical human dev guide, unchanged); upstream `CONTRIBUTING.md` (currently a 4-line stub, gets a one-line discoverability addition).
**Best practices consulted:** [GitHub Blog — *How to write a great AGENTS.md*](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/) (2500-repo analysis, Copilot team); [OpenAI Codex — *Best practices*](https://developers.openai.com/codex/learn/best-practices). Adoption decisions enumerated in the "Editorial pass" and "Content structure" sections below.
**Internal planning doc:** committed to the `docs/agents-md` branch for traceability, not intended for the upstream PR diff. Before pushing to upstream, the spec commit moves off this branch onto a separate `planning/ag-7` branch via `git branch planning/ag-7 docs/agents-md` followed by `git reset --keep <parent>` on `docs/agents-md` so the upstream PR contains only the two file changes (`AGENTS.md` new, `CONTRIBUTING.md` +1 line). Implementation plan codifies the exact sequence.

## Problem

Upstream EMHASS has no vendor-neutral rules file for AI coding agents (Claude Code, Cursor, Aider, Copilot, Codex). Without one, AI tools default to inferred conventions, which produces a recurring pattern documented in the 2026-04-26 schema audit: 8 candidate findings → 4 confirmed bugs (PR-able), 4 needed maintainer judgment (issue-first). Roughly half the AI-driven output reaches the maintainer in a form that wastes review cycles.

`docs/develop.md` is canonical for humans. AGENTS.md fills the orthogonal gap: AI-specific rules, scope corridors, don't-touch zones, and gotchas that humans pick up by osmosis but tools cannot infer from source alone.

## Decision

Ship `AGENTS.md` at the upstream repo root, plus a one-line pointer in `CONTRIBUTING.md`. Direct PR — no preceding issue, since Discussion #808 already cleared the workflow-demo gate for this exact deliverable.

Rejected alternatives:
- *Bundle with AC-5 + AG-onboarding into one Layer-1 docs PR.* AGENTS.md is the only item with explicit maintainer ack. Bundling forces review of unauthorized-scope items and increases the maintainer-fatigue risk we want to avoid.
- *Mini-section in `CONTRIBUTING.md` duplicating AGENTS.md rules.* Two files documenting the same rules drift apart over time. `CONTRIBUTING.md` routes; `AGENTS.md` is the canonical home.
- *Drop hard-coded line numbers, drop file-level refs entirely.* Symbol-level references (`command_line.py::set_input_data`) survive routine code edits and stay grep-able.
- *Issue-first proposal before PR.* Workflow-demo gate already cleared; an additional pre-PR issue burns maintainer attention without adding signal.

## Scope

### Files touched (in fork `OptimalNothing90/emhass`, branch `docs/agents-md`, base `upstream/master`)

| File | Change |
|---|---|
| `AGENTS.md` (new, repo root) | Seven-section vendor-neutral rules document. Structure mirrors AG-7 board body, content cleaned and humanized. |
| `CONTRIBUTING.md` | One-line addition: `For AI coding agents working on EMHASS source, see [\`AGENTS.md\`](AGENTS.md).` Stub otherwise unchanged. |

No other files are touched. Specifically:
- `docs/develop.md` — unchanged. AGENTS.md links to it for setup/workflow content; never restates.
- `docs/study_cases/index.md` — unchanged (no cross-link added in this PR; that lives in AG-onboarding scope).
- `README.md` — unchanged (no AGENTS.md pointer added in this PR).
- `.github/` templates — unchanged.
- `docs/conf.py` / Sphinx tree — unchanged. AGENTS.md is plain Markdown at repo root, not part of the Sphinx build.

### `AGENTS.md` content structure

The file opens with a small frontmatter block, a freshness marker, and a "Repository layout" preamble. Then the seven sections from the AG-7 board body in their original order. Section sizing roughly mirrors the board body, with explicit edits enumerated. None of the seven section *headings* change — the additions live above Section 1 to preserve the structure the maintainer already reviewed.

**Frontmatter (top of file)**
```yaml
---
name: emhass-agents
description: Vendor-neutral rules for AI coding agents working on EMHASS source.
---
```
Two-line YAML, the minimal form GitHub Copilot's AGENTS.md guide treats as required. Cursor and similar tools also parse this. No additional keys beyond `name` and `description`.

**Freshness marker (HTML comment immediately under frontmatter)**
```
<!-- Last verified against upstream/master @ <SHA-7>, <YYYY-MM-DD> -->
```
Future readers can gauge the staleness window without running `git log`. The SHA is recorded at push time, not at spec time. This is invisible in GitHub's rendered view but is the first thing a code-aware reader sees.

**Repository layout (preamble, before Section 1)**
A short prose block listing the directories an agent will touch most:
- `src/emhass/` — core module: `optimization.py`, `forecast.py`, `retrieve_hass.py`, `web_server.py`, `command_line.py`, `utils.py`.
- `tests/` — pytest suite.
- `docs/` — Sphinx source (`develop.md`, `study_cases/`, others).
- `data/` — config defaults and schema (`config_defaults.json`, `associations.csv`).
- `src/emhass/static/` — web UI assets, including `param_definitions.json`.

Codex's best-practices document treats repository layout as required for an effective AGENTS.md. The block is six lines and does not duplicate `docs/develop.md`, which describes setup not layout.

**Section 1 — Canonical commands**
Quick-recall block for AI tools: test command, dependency setup, lint status, docs build, plus a tech-stack mini-table. Explicit pointer to `docs/develop.md` as the canonical source. No roadmap leaks (no "when X lands" wording, no references to internal board IDs).

The tech-stack mini-table pins versions agents need to make library-API decisions:
- Python: per `pyproject.toml` (verify; do not assume).
- Pydantic: v1 at the time of writing — verify in `pyproject.toml`.
- Optimisation: CVXPY (pinned version in `pyproject.toml`).
- Web: Flask.
- Tests: pytest.

Both consulted best-practice guides flag tech-stack versioning as a top-tier item. Saying "Python project" instead of "Python 3.X, Pydantic v1" is the documented anti-pattern.

**Section 2 — Pipeline map**
Two layers, both verified against `upstream/master` HEAD on 2026-04-30:

1. **Public entry-point map** — six rows in a table:
   - Input preparation → `command_line.py::set_input_data_dict`
   - Mode entry, perfect forecast → `command_line.py::perfect_forecast_optim`
   - Mode entry, day-ahead → `command_line.py::dayahead_forecast_optim`
   - Mode entry, rolling MPC → `command_line.py::naive_mpc_optim`
   - Optimisation core → `optimization.py::Optimization.perform_optimization`
   - Publish → `command_line.py::publish_data`
2. **Stage-label pointer** — the codebase uses `stage_timer(stage_times, "<label>", logger)` blocks for finer-grained instrumentation. Five labels: `"pv_forecast"`, `"load_forecast"`, `"price_prep"`, `"optim_solve"`, `"publish"`. Section text instructs the reader to grep `'stage_timer.*"<label>"'` for the live call site, not to memorise line numbers.

This design replaces the original board-body's six-stage abstraction (which assumed standalone `set_input_data` / `forecast_model_fit` / `forecast_load_fit` / `build_lp` / `solve` functions). Reconnaissance against `upstream/master` showed those names do not exist as standalone defs — input prep is one async function with `_dict` suffix, the three optimisation modes are separate entry points, and LP build plus solve live as a single class method inside `Optimization`. The two-layer entry-point + stage-label form is honest about the actual code shape and gives agents grep-targets that survive routine refactoring.

**Section 3 — Don't-touch rules**
Four rules:
1. `action_logs.txt` line format. The web server's error-detection parser depends on the first whitespace-separated token. Format change breaks error reporting.
2. `utils.get_logger` handler accumulation. The function attaches a handler unconditionally; the rule documents the actual behaviour, not a wished-for guard. Stated neutrally, without referencing internal tracking IDs.
3. Two parallel logging subsystems (CLI `utils.get_logger` and Web `app.logger`). Logging changes touch both or neither.
4. `param_definitions.json` — additive changes only. Stated neutrally, no AC-2a/AC-2b/AC-2-fix references.

**Section 4 — Maintainer scope corridors**
Four bullets, sourced from public maintainer statements:
- Threat model from Discussion #808: code injection, not auth-bypass or data-leakage.
- EMHASS as MILP optimiser per Issue #789: vehicle APIs, OCPP, EVCC, charger modulation are out of core scope.
- Glue layer agnostic: Node-RED, MQTT, Home Assistant, generic automations are equivalent integration paths.
- Zero-config default must keep working after every change.

**Section 5 — Limits and gotchas (heart of the document)**
The block David specifically endorsed. Structure preserved:
- "AI tools find code locations, humans decide intent" framing, anchored by the 2026-04-26 audit numbers (8 findings → 4 PR-able, 4 issue-first).
- Issue-first triggers: five concrete bullets covering visible-behavior changes, magic constants, condition-vs-domain-convention questions, and large edits to `optimization.py` / `retrieve_hass.py` / `forecast.py`.
- Always verify before claiming done: sign conventions, units, reproducer present, container/UI smoke-test for schema or web-server changes.
- Do-not-refactor-without-issue: large file restructures, public API renames, new dependencies.
- Adding a parameter: pointer to `docs/develop.md`'s 4-step workflow. Not restated.
- Common AI-tool failure modes: four concrete examples — confusing `param_definitions.json` with `config_defaults.json`, inventing solver APIs, mixing Pydantic v1/v2 patterns, writing synchronous wrappers around the async `command_line.py` entry points.
- Token / context limits: large source files (`optimization.py`, `command_line.py` at 3000+ LOC each); `repomix` mentioned as an on-demand vendor-neutral tool, not a committed artefact.

**Section 6 — Conventions**
Two bullets in the final file:
- Documentation style: soft Diátaxis, with pointer to `docs/study_cases/` as the worked example.
- Commit-message prefix convention (`fix`, `docs`, `feat`, `chore`) per recent maintainer practice.

The board body contains a third "Account hygiene" bullet (gh auth switching for dual-account contributors). That bullet is contributor-personal workflow and does not appear in the upstream file — it is dropped, not rephrased.

**Section 7 — Where to find more**
Four links:
- `docs/develop.md` — canonical EMHASS dev guide. Read first.
- `llms.txt` at `https://emhass.readthedocs.io/en/latest/llms.txt` — Sphinx-generated routing manifest (output of PR #792). Hosted on Read the Docs because the file does not exist in the source tree; it is built per Sphinx run.
- `docs/study_cases/` — Diátaxis-soft worked examples per persona.
- Project board: `https://github.com/users/davidusb-geek/projects/2` — public, maintainer-owned coordination view with scope corridors visible per card.

### Editorial pass

**Strip from board-body source (internals hygiene):**
- Internal board IDs: `AC-2a`, `AC-2b`, `AC-2-fix`, `AM-5`, `U-4`, `AG-onboarding`. Replaced with neutral wording or removed.
- Roadmap leaks: any "when X lands" phrasing, any "pending" tracking comment that references internal IDs.
- Account-hygiene line in Section 6 (contributor-personal, not upstream-relevant).
- The Section 1 ruff line ("Lint: ruff (when AM-5 lands; until then, no enforced linter)") replaced with: "Lint: no enforced linter at the time of writing."

**Humanizer-full pass after content is otherwise final:**
- Em-dash overuse: the board body has roughly twenty em-dashes across seven sections. Cut to a handful. Replacements use comma, period, or parentheses depending on the rhythm.
- Rule-of-three list scan. Where bullet groups feel artificially triadic, break or expand.
- AI-vocabulary scan: `leverage`, `robust`, `comprehensive`, `delve`, `seamless`, `streamline`, `cutting-edge`, `state-of-the-art`. Replaced with concrete verbs or removed.
- Vague attribution: "research shows", "studies indicate", and similar are either anchored to a concrete issue/discussion number or struck.
- Filler phrases: `in order to` → `to`; `due to the fact that` → `because`; `at this point in time` → `now` (or struck).
- Negative-parallelism: "not X but Y" patterns checked for over-use.

**What stays unchanged:**
- The concrete examples — that is what the maintainer endorsed.
- Code blocks, symbol references, issue/discussion numbers, the 8/4 audit statistic.

**Tone target:** prose that reads like a longtime contributor writing a short memo for other contributors. Not fragmenty, not buzzy.

**Length cap:** 350 source lines for the rendered file (frontmatter + freshness marker + Repository layout + seven sections). The OpenAI Codex best-practices guide cites a one-to-three-page maximum and observes that longer files reduce adoption. 350 lines is the upper bound; the spec aims for closer to 250 in practice. If the draft exceeds 350, trim Section 5 examples first (longest section) before touching the schema-relevant sections 2 / 3 / 4.

**Voice / spelling:** match upstream voice. Existing maintainer texts use British spelling (`optimiser`, `behaviour`, `colour`, `analyse`). The humanizer pass enforces this — any US-variant spellings introduced during drafting are corrected before push.

## Data flow (after PR merges)

```
AI coding agent opens upstream/emhass repo
        │
        ▼  reads (by convention) AGENTS.md at repo root
rules-for-AI loaded into agent context
        │
        ▼  also reads CONTRIBUTING.md (universal entry point)
one-line pointer confirms AGENTS.md is canonical for AI rules
        │
        ▼  AGENTS.md Section 7 routes
        ├─→ docs/develop.md  (canonical human dev guide, setup + workflows)
        ├─→ llms.txt          (Sphinx-built routing manifest)
        ├─→ docs/study_cases/ (Diátaxis-soft worked examples)
        └─→ Project board     (scope corridors + coordination)
```

Default behavior for existing humans (no AGENTS.md awareness): unchanged. They follow `CONTRIBUTING.md` → `docs/develop.md` as before. The added line in `CONTRIBUTING.md` is one sentence at the end and does not change human flow.

## Verification before push

A pre-push checklist runs in this order:

1. **Symbol references in Sections 2 and 3.** Each `<file>::<function>` pair grepped against fresh `upstream/master`. If a symbol does not exist by that name, correct it or rephrase the reference. No raw line numbers anywhere in the file.
2. **Links.** All HTTP links resolve (Issue #789, Discussion #808, Project board, diataxis.fr, the Read the Docs `llms.txt` URL). All in-repo paths exist (`docs/develop.md`, `docs/study_cases/`). Anchor links into `develop.md` (if any) point at headings that currently exist there.
3. **Doc-complementarity check.** AGENTS.md does not restate develop.md content. Specifically: the Section 1 quick-recall lists commands but does not describe environment setup steps; the Section 5 "adding a parameter" entry links and does not restate the four steps; no AGENTS.md sentence contradicts a develop.md sentence on the same topic.
4. **Humanizer skill pass.** Run the humanizer skill over the full `AGENTS.md` content. Review the diff. Apply the changes that improve naturalness; reject any that strip concreteness.
5. **Account switch.** `gh auth status` shows `OptimalNothing90` as active before `git push -u origin docs/agents-md`. After the PR is open, `gh auth switch --user mschaepers`.
6. **Diff sanity.** `git diff upstream/master..docs/agents-md` shows exactly two file changes: `AGENTS.md` (new) and `CONTRIBUTING.md` (+1 line). No submodule drift, no `.gitignore` churn, no LF/CRLF mass-diff.
7. **Length cap.** `wc -l AGENTS.md` returns at most 350. If exceeded, trim Section 5 examples first.
8. **Spelling variant.** `grep -nE 'optimiz|behavior|color|analyz' AGENTS.md` returns no matches. British spelling holds throughout.
9. **Frontmatter parses.** The opening YAML block validates as YAML (`python -c "import yaml; yaml.safe_load(open('AGENTS.md').read().split('---')[1])"` succeeds).
10. **Freshness marker filled.** The HTML comment carries an actual SHA and date, not a placeholder.
11. **GitHub render preview.** After `git push`, open the PR as draft and view `AGENTS.md` rendered on github.com. Tables, code-fences, and links display correctly. Mark the PR ready only after this passes.

## Branch and PR

- Base: `upstream/master`, freshly fetched.
- Branch (in `OptimalNothing90/emhass`): `docs/agents-md`.
- PR title: `docs: add AGENTS.md (vendor-neutral rules for AI coding agents)`.
- PR target: `davidusb-geek/emhass:master`.
- PR body, in order:
  - One-paragraph rationale (problem + decision).
  - Reference to Discussion #808 reply with the maintainer's exact ack quote.
  - Explicit doc-complementarity statement: "does not duplicate `docs/develop.md`".
  - Statement of best-practice sources consulted (the GitHub Copilot 2500-repo blog and OpenAI Codex best-practices), so reviewers see the AGENTS.md was not improvised.
  - Pre-push verification checklist (the eleven items from "Verification before push") as a checked Markdown task list. Evidence of self-review at-a-glance, not a "trust me" PR.
- No preceding issue.

## Out of scope

- AC-5 (`llms-full.txt` extension over PR #792 surface). Separate plan, separate PR, after AGENTS.md merges and the maintainer reaction is observed.
- AG-onboarding (human-facing contributor doc, including `CONTRIBUTING.md` rewrite beyond the one-line pointer).
- Cross-link from `docs/study_cases/index.md` back to `AGENTS.md`. Lives in AG-onboarding.
- `README.md` update with an AGENTS.md pointer.
- `.github/` PR or issue templates that ask AI-tool users to disclose tooling.
- Pre-PR proposal issue.
- Sphinx-build integration of `AGENTS.md` (it stays at repo root as plain Markdown).
- Any roadmap or "track via X" references inside the final file.
- Account-hygiene workflow text inside the final file (contributor-personal, separate concern).

## Pacing follow-up (outside this spec)

After AGENTS.md is opened as a PR, observe the maintainer's response before starting AC-5 or AG-onboarding work. The intent is to keep the AI-driven contribution rate from feeling like a flood. Concrete signal-to-action mapping:

- Merge with no comment, or merge with positive comment → start AC-5 plan next.
- Merge with reservations or scope pushback → pause AC-5 and AG-onboarding, run brainstorming again with the new constraints.
- No response within roughly two weeks → ping politely once on the PR, then wait.

This is informational for the implementation plan, not a requirement of this spec.
