# AG-onboarding — AI-coder contributor onboarding doc — Design

**Date:** 2026-05-11
**Card:** `AG-onboarding` (board/items.json)
**Issue:** None — corridor-blessed in Discussion [#808](https://github.com/davidusb-geek/emhass/discussions/808) (Layer-1 AI-coder-friendly docs)
**Audit source:** None — item body extensively pre-detailed (6-section structure, tone-guide, deps explicit)
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Branch:** `docs/ag-onboarding`
**Effort:** M
**Phase / Priority:** Phase 1.5 / P1
**Goal-fit:** (empty — non-goal hygiene, maintainer-corridor-blessed)

## 1. Problem

EMHASS contributors increasingly use AI coding agents (Claude Code, Cursor, Aider, Copilot, web-based Claude) to read source, propose changes, draft PRs. `AGENTS.md` (PR #831, merged 2026-04-30) carries vendor-neutral rules for the agent itself — but does not address the *human driving the agent*. New AI-coder contributors run into recurring landmines that AI does not flag: sign-conventions on power columns (P_grid, P_batt), HA-scaling traps (SOC ×100 vs fraction), MILP infeasibility symptom-vs-cause confusion, the `q_input_start=0` thermal-battery landmine (PR #785 prior art), dual logger subsystems (CLI + Web) that must be touched together, the `OptimizationCacheKey` 4-step "adding a parameter" workflow that AI tools forget. Each of these has cost contributors hours or caused review-friction PRs. There is no contributor-facing companion to AGENTS.md teaching humans what AI will not tell them.

## 2. Goal

Ship `docs/develop_ai_coders.md` — a ~1500-word human-facing companion to AGENTS.md that teaches the AI-coder contributor: (1) which tool to drive on EMHASS and how, (2) decision-tree for issue-first vs PR-direct with real-upstream-PR examples, (3) seven EMHASS-specific landmines AI will not flag, (4) pre-PR self-check, (5) red-flags meaning stop-and-ask, (6) where to find help. Cross-linked from `CONTRIBUTING.md` + `AGENTS.md` preamble + Sphinx toctree for discoverability. Written in caveman-full style (terse, fragments OK, no fluff) to match the dense-rule-doc convention AGENTS.md set — with Auto-Clarity exceptions for multi-step sequences where fragment order would risk misread.

## 3. Decisions

| # | Decision | Source |
|---|----------|--------|
| D1 | **Target file: `docs/develop_ai_coders.md`** — flat sibling of `develop.md`, naming-pairing clear (general / AI-extension). Skip `docs/contributing/` subfolder — would be the first meta-subfolder (existing subfolders `study_cases/` / `cookbook/` / `api/v1/` are content-categories, not contributor-meta), structure change Maintainer has not endorsed. Q1 brainstorm. | session 2026-05-11 |
| D2 | **Decision-tree format: ASCII-art in fenced block.** No new Sphinx dependency (mermaid not in extensions; existing extensions are `autodoc`, `myst_parser`, `sphinx_design`, `sphinx_llms_txt`). ASCII renders in any Sphinx setup, scan-friendly, no scope-creep. Q2 brainstorm. | session 2026-05-11 |
| D3 | **AI-tool coverage: Claude Code primary + Cursor/Aider stubs marked "tested-against: untested — contribution welcome".** Author runs Claude Code in production, can authentic-verify. Cursor/Aider stubs preserve completeness signal without overclaim. Same precedent as cookbook D4a (no HA snippets). Q3 brainstorm. | session 2026-05-11 |
| D4 | **Examples = real upstream PR-refs for click-through teaching.** Concrete: [#817](https://github.com/davidusb-geek/emhass/pull/817) (typo fix, PR-direct), [#831](https://github.com/davidusb-geek/emhass/pull/831) (AGENTS.md, corridor-#808 first), [#835](https://github.com/davidusb-geek/emhass/pull/835) (plan-output schema, issue-#828 first), [#836](https://github.com/davidusb-geek/emhass/pull/836) (Cookbook, Discussion-#824 alignment first), and cautionary [#830](https://github.com/davidusb-geek/emhass/pull/830) (no-issue-first → maintainer A/B-direction pushback). NOT private board IDs (U-1/U-3/AC-2a from item body — would leak internal taxonomy). Q4 brainstorm. | session 2026-05-11 |
| D5 | **Cross-link strategy: 3-way discoverability** — `CONTRIBUTING.md` +1 line, `AGENTS.md` preamble +1 italics-line, `docs/index.md` (or section-reference) toctree +1 entry. CONTRIBUTING.md is GitHub-convention entry-point. AGENTS.md cross-link signals companion exists without polluting agent-rules. Toctree integrates with Sphinx docs-site. Three minimal edits, 1 line each. Q5 brainstorm. | session 2026-05-11 |
| D6 | **Length: strict ~1500 words.** Meta-docs decay with growth. ~1500w = 6-8 min reading time = reasonable one-time-onboarding-read. Section-budgets enforced per D7. Overruns cut content, not expand cap. Q6 brainstorm. | session 2026-05-11 |
| D7 | **Section-budgets:** Intro ~100w / S1 AI-tool-setup ~300w (200 Claude Code + 50+50 Cursor/Aider) / S2 Decision-tree ~250w (ASCII-tree + real-PR prose) / S3 Landmines ~400w (7 × ~55w) / S4 Self-check ~150w / S5 Red-flags ~150w / S6 Help-resources ~100w / Footer ~50w. | derived from D6 |
| D8 | **Style: caveman-full applied to artifact.** Drop articles, fragments OK in lists, terse synonyms, no filler / pleasantries / hedging. Matches AGENTS.md dense-rule-doc convention. Auto-Clarity exceptions per Skill rule: multi-step instructions ("if X, do Y, then Z") use normal grammar for clarity; code blocks unchanged; warnings/landmines caveman OK; checklists caveman OK; tables caveman OK. | session 2026-05-11 |
| D9 | **Style-risk mitigation: on maintainer style-reject, pivot to concise-professional** on same branch in review-feedback-roundtrip. No-new-PR cost = 1 patch commit. Risk explicit in PR description so maintainer can vote-with-feet pre-merge. | session 2026-05-11 |
| D10 | **Skip `repomix` entirely** — neither tool nor `repomix.config.json`. Author does not use it (Claude Code native `Read`/`Glob`/`Grep` covers context-loading). Per cookbook precedent (no HA snippets without authentic testing): don't recommend untested tools. Modern AI-coder tools have native file-tools; repomix friction > benefit for that demographic. Q7 brainstorm. | session 2026-05-11 |
| D11 | **Privacy baseline: cookbook-pattern lint applies.** No `loxone`, no private IPs, no `loxonesmarthome` strings, no `V4.x` internal-version-tags, no `Ottenhofen` / lat-lon / kWp specifics, no secret env names. Plus AG-onboarding-specific: NO private board-IDs (U-1, U-3, AC-2a, AG-7 internal-ref etc. — use real upstream PR/issue numbers instead). | `feedback_pr_review_in_fork_session`; cookbook precedent |
| D12 | **Soft-dep placeholders.** Ruff IS enforced today (`uvx ruff check .` via `.github/workflows/code-quality.yml`) — doc states current state. AM-5 pre-commit-local addition = "TBD when AM-5 lands" marker. AG-B1 public skill-plugin link = "TBD when AG-B1 ships" marker. AC-5 llms-full.txt picks up new doc automatically via Sphinx toctree — no manual coordination. | AGENTS.md L26 (ruff enforced); AM-5/AG-B1/AC-5 board status |
| D13 | **Source-verify landmines in plan, not spec.** Spec lists which 7 landmines covered. Plan tasks each landmine with `src/emhass/...:LINE` citations (sign conventions in `optimization.py` constraint code, SOC scaling in `command_line.py:2329` ×100 call, q_input_start in PR #785, dual logger in `command_line.py` + `web_server.py`, OptimizationCacheKey grep-trace). Per `feedback_source_resolve_first`. | session 2026-05-11 |
| D14 | **No new file in `docs/contributing/`** (decision against D1 alternative). Single new file under existing flat `docs/` tree. Reduces structural-commitment to Maintainer-not-endorsed meta-subfolder pattern. | D1 follow-through |

## 4. Files touched

- **NEW:** `docs/develop_ai_coders.md` — the doc, ~1500 words
- **MOD:** `CONTRIBUTING.md` — +1 line cross-link after existing AGENTS.md link
- **MOD:** `AGENTS.md` — +1 italics-line in preamble, after existing description, before Section 1
- **MOD:** `docs/index.md` OR `docs/section_reference.md` (verify in Phase 2 source-trace) — toctree gets `develop_ai_coders` entry, sibling to `develop`

## 5. Concrete edits

| File | Edit | Detail |
|------|------|--------|
| `docs/develop_ai_coders.md` | create | ~1500 words across Intro + 6 Sections + Footer per D7 budgets. Caveman-full style per D8. Sections per item body: AI-tool-setup / decision-tree / landmines / self-check / red-flags / help-resources. Real upstream PR-refs per D4. No `repomix` mention per D10. Soft-dep markers per D12. |
| `CONTRIBUTING.md` | mod, +1 line | After existing line `For AI coding agents working on EMHASS source, see [\`AGENTS.md\`](AGENTS.md).`, add:<br>`Driving an AI coding agent on this codebase? See [\`docs/develop_ai_coders.md\`](docs/develop_ai_coders.md) for human-side guidance.` |
| `AGENTS.md` | mod, +1 italics-line | In preamble (after the description block, before `## Repository layout` heading at ~L11), add:<br>`*Humans driving an agent on this codebase: see [\`docs/develop_ai_coders.md\`](docs/develop_ai_coders.md) for the contributor-side companion to this file.*` |
| `docs/index.md` (or `docs/section_reference.md`) | mod, +1 toctree entry | Locate the toctree containing `develop`. Insert `develop_ai_coders` immediately after `develop` (peer, not nested). Verify which file owns that toctree in Phase 2 source-trace — likely `section_reference.md` based on existing structure. |

## 6. Test strategy

Documentation-only PR. No runtime tests.

- **Privacy lint** (mandatory): grep for cookbook-baseline pattern + AG-onboarding-specific patterns (private board-ID prefixes `U-`, `AC-`, `AG-`, `EV-`, `AM-`, `CE-` when followed by digits in inline-text references). Expect: zero matches except in the explicit "real upstream PR-refs" code-block contexts.
- **Length lint**: `wc -w docs/develop_ai_coders.md` must be in `[1300, 1700]` range. Strict per D6.
- **Sphinx build**: `cd docs && ./make.bat html` (or `sphinx-build -b html docs docs/_build/html`). Must succeed without warnings naming the new file or modified files.
- **Render check**: open `_build/html/develop_ai_coders.html`. ASCII-tree renders in monospace block. Real PR-refs are clickable links. Toctree-entry shows in `index.html` navigation. Cross-link in CONTRIBUTING.md renders. Cross-link in AGENTS.md renders.
- **Source-verification (D13)**: each of the 7 landmines in Section 3 carries a citation to the upstream source (file:line OR PR-ref). Plan Task 2 source-traces each citation.
- **Style spot-check**: doc reads as caveman-full per D8. Multi-step instructions use normal grammar per Auto-Clarity exception.
- **No automated test added.** Per AC-1 / DOC-cookbook precedent: docs PRs don't carry unit tests.

## 7. Acceptance criteria

1. `docs/develop_ai_coders.md` exists, length in `[1300, 1700]` words (strict cap per D6).
2. Document structure follows D7 section-budgets: Intro + 6 Sections + Footer.
3. Section 1 covers Claude Code authentic + Cursor/Aider stubs with "tested-against: untested — contribution welcome" markers (D3).
4. Section 2 carries an ASCII-art decision-tree in fenced code-block (D2) + real-upstream-PR examples per branch (D4).
5. Section 3 covers all 7 landmines: sign conventions, SOC scaling, MILP infeasibility, q_input_start=0, dual logger, OptimizationCacheKey, source-resolve-discipline.
6. Each landmine in Section 3 carries a `src/emhass/...:LINE` citation OR a real-PR-ref citation per D13.
7. Section 4 (self-check) is a 7-item bullet-list checklist.
8. Section 5 (red-flags) is a bullet-list of stop-and-ask patterns.
9. Section 6 (help-resources) includes links to GitHub Discussions, `docs/develop.md`, maintainer-corridor refs #808 / #789. NO repomix mention (D10).
10. `CONTRIBUTING.md` +1 line cross-link to `docs/develop_ai_coders.md` (D5).
11. `AGENTS.md` preamble +1 italics-line cross-link (D5).
12. `docs/index.md` OR `docs/section_reference.md` toctree includes `develop_ai_coders` as peer of `develop` (D5).
13. Privacy lint: zero matches against baseline pattern + AG-onboarding-extension pattern (D11).
14. Sphinx build clean.
15. PR description acknowledges the caveman-style-risk per D9 + invites maintainer to flag if style-pivot needed.

## 8. Out of scope

- `repomix` tool, `repomix.config.json` file, any repomix-related content (D10).
- New `docs/contributing/` subfolder (D14).
- AC-5 llms-full.txt explicit cross-coordination — auto-pickup via Sphinx toctree (D12 footnote).
- AGENTS.md content-changes beyond the 1-line preamble cross-link.
- Cursor / Aider tooling QA — author cannot authentic-test (D3).
- AG-B1 public-skill-plugin authoring — that is AG-B1's own scope; doc mentions skill-plugin-link as "TBD when AG-B1 ships" marker.
- AM-5 pre-commit-local addition — that is AM-5's scope; doc treats `.pre-commit-config.yaml` as "TBD when AM-5 lands".
- Translations — English only.
- Maintainer corridor-extension beyond #808 Layer 1 — that is corridor-block's own concern.
- Section-by-section style-evaluation against AGENTS.md tone — common spirit, no formal diff.

## 9. References

- Maintainer corridor: [emhass#808](https://github.com/davidusb-geek/emhass/discussions/808) (Layer-1 AI-coder-friendly docs)
- Sibling corridor: [emhass#789](https://github.com/davidusb-geek/emhass/discussions/789) (scope-corridor agreement)
- Hard-dep PR (merged): [emhass#831](https://github.com/davidusb-geek/emhass/pull/831) (AGENTS.md introduction, 2026-04-30)
- Example PRs for D4 decision-tree teaching: [#817](https://github.com/davidusb-geek/emhass/pull/817), [#814](https://github.com/davidusb-geek/emhass/pull/814), [#831](https://github.com/davidusb-geek/emhass/pull/831), [#835](https://github.com/davidusb-geek/emhass/pull/835), [#836](https://github.com/davidusb-geek/emhass/pull/836), [#830](https://github.com/davidusb-geek/emhass/pull/830) (cautionary)
- Landmine prior art: [#785](https://github.com/davidusb-geek/emhass/pull/785) (q_input_start=0 thermal-battery infeasibility)
- Sibling board items: AC-5 (llms-full.txt, Todo) — auto-picks-up via toctree; AM-5 (DevX-stack modernisation, Ideas) — pre-commit-local TBD; AG-B1 (public skill plugin, Ideas) — skill-plugin-link TBD
- Memory: `feedback_pr_first_for_strategic.md`, `feedback_branch_naming.md` (`docs/ag-onboarding`), `feedback_source_resolve_first.md` (D13), `feedback_pr_review_in_fork_session.md` (privacy + session resumability), `project_cookbook_recipe_queue.md` (privacy lint baseline pattern), `project_parked_fork_sessions.md` (precedent for parked-session-tracking)
- Primary source for landmine verification (per D13): `src/emhass/optimization.py` (battery constraints, MILP infeasibility patterns, q_input_start handling), `src/emhass/command_line.py` (SOC ×100 at line ~2329, dual-logger-subsystem grep, OptimizationCacheKey grep), `src/emhass/web_server.py` (dual-logger-subsystem grep), `src/emhass/utils.py` (`stage_timer`, parameter wiring)
- Convention precedent: `AGENTS.md` (dense rule-doc tone, structured tables), `docs/develop.md` (general-developer guide), `docs/cookbook/_template.md` (contributor-rules format)
