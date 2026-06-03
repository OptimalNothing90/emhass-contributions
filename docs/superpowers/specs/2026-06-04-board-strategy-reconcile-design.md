# Board ↔ Strategy Reconcile — Design Spec

**Date:** 2026-06-04
**Author:** OptimalNothing90 (Mauricio) + Claude
**Board:** `davidusb-geek/projects/2` (`PVT_kwHOAfZrVs4BV1jU`) — David's **public** project
**Status:** Approved in brainstorm 2026-06-04, pending spec review

## Problem

The board design (`board/design.md` v2.0, 2026-04-28) predates the EVCC strategic
pivot. Three drifts:

1. **Stale roadmap calendar** — all Phase date-targets (§5) are in the past; Phase 4 is
   still themed "EV-Coupling (local)", which the pivot superseded (EMHASS = whole-house
   planner, evcc = executor; shared-plan registry per RFC 0001 / Discussion #931).
2. **Strategy invisible on board** — the two strategic goals (LLM-ready, EV-EVCC) and the
   EVCC-registry track live only in memory + a committed RFC file. The live #875
   regression work (#933/#934/#938/#935/#936) is not carded, breaking the historical
   per-PR carding practice.
3. **Speculative backlog ballast** — Phase-5 holds several L/XL, non-goal, no-near-path
   ideas that inflate the board and obscure real priorities.

Goal: board = current truth. Add what matters, cut what doesn't, re-baseline phases.

## Constraints

- **Public board.** Everything is visible to David + the public. No private strategy
  (the Ensemble/BATNA glue layer) gets carded. Epic card bodies stay public-neutral.
- **Maintainer-originated ideas are not unilaterally rejected.** CE-7 came from David
  (#789) → not cut.
- **Account:** mutations require `gh` user `OptimalNothing90` (already active).
- **Workflow hard-rule:** `python fetch.py` (real) + commit sync **before** any mutation
  script; dry-run drift must be 0 after.

## Decisions (brainstorm 2026-06-04)

| Topic | Decision |
|-------|----------|
| Review lens | Full reconcile (add + cut + re-baseline) |
| Cut mechanism | Move to terminal `Done / Won't Do` |
| EVCC/epic granularity | Lean — 2 goal-epics only; downstream (sibling RFCs, public example) NOT carded until #931 resonance; Ensemble glue NOT carded (private) |
| #875 PRs | Card them (linked issues/PRs), board = truth |
| Phases | Drop date-targets; re-theme Phase 4 → "EVCC Integration"; doc-only (Phase field option names are bare numbers) |

## Design

### A. Cuts → `Done / Won't Do` (5 items)

All are Draft cards → status move only, no GitHub issue close. Cards remain for audit
trail and are revivable.

| Item | Eff/Pri | Rationale |
|------|---------|-----------|
| AM-6 Persistent storage (LMDB/SQLite) | XL P3 | Speculative, non-goal, no near path |
| AG-8 `emhass init` Setup-Wizard CLI | L P3 | Non-goal nice-to-have |
| AM-3 Provider-Abstraction pilot | L P2 | Large refactor, merge-conflict risk, maintainer may reject |
| AG-5 emhass-calibrate skill | M P2 | Speculative local skill, no demand |
| AC-8 errors.yaml + error_catalog framework | L P2 | Chicken-egg; consumers (AG-4/AG-9) work standalone |

**Kept in Ideas (explicitly, not cut):** AG-9 (LLM-ready-relevant), CE-7 (David's idea),
AM-4 (revivable post-#931), AM-5 (harmless DevX hygiene).

**Consistency cleanup from cutting AC-8:** AC-8 was referenced as "foundation" by AG-4 and
AG-9. De-reference it from those two card bodies (idempotent body edit) so the board does
not point at a Won't-Do item. AG-4/AG-9 stand alone with inline hints.

### B. Adds

**B1 — Goal epic: LLM-ready** (new Draft card)
- Fields: Category `A: Code-Lifecycle`, Phase `Phase 3`, Priority `P1`, Effort `L`,
  Scope `Discussion-Only`. Status `In Progress`.
- Body: the goal (machine-readable EMHASS for coding agents + LLM consumers), the
  member items it groups (AC-2 / AC-2c / AM-1 / AM-1b / AM-2 / AM-7, plus future
  llms.txt), and a done-criterion (schema spine published + openapi runtime payloads +
  config.md auto-generated, no drift).

**B2 — Goal epic: EV-EVCC** (new Draft card)
- Fields: Category `B: End-User-Ops`, Phase `Phase 4`, Priority `P1`, Effort `XL`,
  Scope `Discussion-Only`. Status `In Progress`.
- Body: EMHASS = whole-house planner, evcc = executor; shared-plan registry per RFC 0001
  (links Discussion #931); currently awaiting community/David resonance. Member items:
  EV-9 (cookbook recipe), CE-7 (GUI EV-section). **Public-neutral — no Ensemble/BATNA
  mention.**

**B3 — #875 regression cards** (add as linked content via `addProjectV2ItemById`)
- `#933` P_Load KeyError — Phase 2, Upstream, Status In Progress (READY)
- `#934` restore inverter 5000 default — Phase 2, Upstream, Status In Progress (Draft, gated on David)
- `#938` Windows-CI timeout flake — Phase 2, Upstream, Status In Progress (READY)
- `#935` SOC%-clamp-vs-reject — Phase 2, Upstream, Status Candidates (David's call)
- `#936` set_nodischarge_to_grid E<=D over-constraint — Phase 2, Upstream, Status Candidates (David + torsteinelv)

Node IDs resolved at implementation time via `gh issue view <n> --json id`.

### C. Phase re-baseline (`board/design.md` edits only)

- §5 Phase Targets: drop the **Target** date column; restate Phase as pure cross-repo
  sequencing (no calendar). Add a one-line note that dates proved aspirational and were
  retired 2026-06-04.
- §5 Phase 4 theme: "EV-Coupling (local)" → **"EVCC Integration"** (whole-house planner /
  evcc executor framing). Phase 5 theme note: "thinned after 2026-06-04 cut".
- §1, §5, §7: remove stale `EV-1..7` references (only EV-9 survives as a card) and the
  old local-coupling framing.
- No GitHub Phase-field mutation needed — option names are bare numbers.

## Components / Artifacts

1. `board/2026-06-04-reconcile-cuts.py` — move 5 cards to Won't Do (guarded by
   expected-status), de-reference AC-8 from AG-4/AG-9 via `append_to_body_idempotent` or
   a targeted body rewrite.
2. `board/2026-06-04-reconcile-adds.py` — create 2 goal-epic draft cards
   (`add_draft_to_project`) + set their fields; add 5 #875 issues/PRs as linked content +
   set Phase/Scope/Status fields.
3. `board/design.md` — §1/§5/§7 edits (manual via Edit).
4. `board/items.json` — refreshed by each mutation script's `save_items`.

Each artifact mirrors the existing dated-script idiom (`lib.py` helpers, PROJECT_ID
constant, expected-status guard, print receipts, `save_items`).

## Data Flow

```
fetch.py (real) → commit sync → cuts.py → fetch --dry-run (0 drift) → commit
                                adds.py → fetch --dry-run (0 drift) → commit
                                design.md edits → commit
```

## Error Handling

- Every status/field mutation guarded by `expected_current_status` check; print `SKIP`
  and continue on mismatch (matches `2026-05-11-promote-tier1-tier2.py`).
- `addProjectV2ItemById` is idempotent per (project, content) — re-run returns the
  existing item id; safe.
- Goal-epic creation is NOT idempotent (`addProjectV2DraftIssue` always creates). Guard:
  before creating, check `items.json` for an existing card with the same title; skip if
  present. Prevents double-create on re-run.

## Testing / Verification

- `python fetch.py --dry-run` after each script → must report `0 changed` (live == json).
- Read-back: confirm 5 cards in Won't Do, 2 epics + 5 #875 cards present with correct
  fields, AC-8 de-referenced from AG-4/AG-9 bodies.
- `board/next.py` still runs clean (no schema break in items.json).
- `git diff board/design.md` review before commit.

## Out of Scope

- Sibling RFCs (priority/template/MQTT), public EV-demand example — gated on #931
  resonance, not carded now.
- Ensemble/BATNA private glue layer — never on the public board.
- GitHub Phase-field option mutation — not needed.
- Any upstream code change — this is board + doc curation only.
