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
| Folded themes (2026-06-04) | Add 3rd epic **Reliability** + flagship card *Optim feasibility smoke-gate*; battery-constraint + forecast-fetch = Reliability pillars (reference existing cards, no new epics); runtime-config-validation folds into LLM-ready epic; AGENTS.md-enforcement added as gated Ideas card; **AG-8 reframed** (CLI wizard → schema-driven web-config, LLM-ready member, not cut); **T5 resonance-accelerator NOT carded** (gated on #931, stays internal strategy note) |

## Design

### A. Cuts → `Done / Won't Do` (4 items)

All are Draft cards → status move only, no GitHub issue close. Cards remain for audit
trail and are revivable.

| Item | Eff/Pri | Rationale |
|------|---------|-----------|
| AM-6 Persistent storage (LMDB/SQLite) | XL P3 | Speculative, non-goal, no near path |
| AM-3 Provider-Abstraction pilot | L P2 | Large refactor, merge-conflict risk, maintainer may reject |
| AG-5 emhass-calibrate skill | M P2 | Speculative local skill, no demand |
| AC-8 errors.yaml + error_catalog framework | L P2 | Chicken-egg; consumers (AG-4/AG-9) work standalone |

**AG-8 reframed, NOT cut** — the `emhass init` Setup-Wizard **CLI** framing is dead (a CLI
wizard duplicates EMHASS's existing web config page). Repurposed → **schema-driven
web-config** (see B7): `param_definitions.json` drives docs (AM-2) + validation (T6) +
the config form/UI. This makes it goal-aligned (LLM-ready: single schema → many surfaces)
instead of an isolated human wizard.

**Kept in Ideas (explicitly, not cut):** AG-9 (LLM-ready-relevant), CE-7 (David's idea),
AM-4 (revivable post-#931), AM-5 (harmless DevX hygiene).

**Consistency cleanup from cutting AC-8:** AC-8 was referenced as "foundation" by AG-4 and
AG-9. De-reference it from those two card bodies (idempotent body edit) so the board does
not point at a Won't-Do item. AG-4/AG-9 stand alone with inline hints.

### B. Adds

**B1 — Goal epic: LLM-ready** (new Draft card)
- Fields: Category `A: Code-Lifecycle`, Phase `Phase 3`, Priority `P1`, Effort `L`,
  Scope `Discussion-Only`. Status `In Progress`.
- Body: the goal (machine-readable EMHASS for coding agents + LLM consumers), framed as
  **single schema → many generated surfaces**. Member items: AC-2 / AC-2c / AM-1 /
  AM-1b / AM-2 (docs), **AG-8-reframed** (config UI, see B7), plus future llms.txt and
  **runtime config-validation [T6]** — Pydantic/jsonschema validation of merged config
  against `param_definitions.json` with clear errors; attacks the #869 null-default
  class. Done-criterion: schema spine published + openapi runtime payloads + config.md
  auto-generated + config validated at load + config form schema-driven, no drift.

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

**B4 — Goal epic: Reliability / Regression-Harness** (new Draft card) — folded theme T1
- Fields: Category `Infra`, Phase `Phase 3`, Priority `P1`, Effort `XL`, Scope
  `Discussion-Only`. Status `In Progress`.
- Body: reliability is the floor under both strategic goals; the v0.17.x contributor
  wave + our own #830→#875 regression show happy-path-only changes reach production.
  Pillars:
  1. **Optim feasibility smoke-gate** [flagship, B5] — would have caught #875 + #869.
  2. **Schema drift-guard** — AM-7 (param_definitions ↔ config_defaults), existing card.
  3. **Battery-MILP constraint correctness [T3]** — references existing cards #875 /
     #935 / #936 / ISSUE-807-U-2; the SoC-clamp + `set_nodischarge_to_grid` + dynamic
     charge-power issues all cluster in the battery constraint set.
  4. **Forecast-fetch resilience [T4]** — references U-3 / U-5 / U-6; consistent
     timeout/retry/fallback across all `forecast.py` providers.
- Public-neutral. AM-7 moves from the LLM-ready epic's member list to here.

**B5 — Optim feasibility smoke-gate (CI)** (new Draft card) — flagship of B4
- Fields: Category `A: Code-Lifecycle`, Phase `Phase 3`, Priority `P1`, Effort `M`,
  Scope `Upstream`. Status `Candidates` (well-scoped, proposable to David; can ride
  alongside AM-7).
- Body: a CI job that runs a full optimization over a small matrix of reference configs
  (incl. hybrid + battery) and asserts the run is feasible and key outputs are within
  sane bounds. Catches the regression class #875 (hybrid infeasible) and #869.

**B6 — AGENTS.md enforcement tightening** (new Draft card) — folded theme T2
- Fields: Category `A: Code-Lifecycle`, Phase `Phase 3`, Priority `P2`, Effort `S`,
  Scope `Upstream`. Status `Ideas` (gated — do NOT promote yet).
- Body: make `check_def_loads` mandatory + add vanilla-optim-smoke reference in
  AGENTS.md; honor-system → enforced. **Gated on #886 + #900 landing** so AGENTS.md can
  point at real enforcement. Card exists for visibility only until then.

**B7 — AG-8 reframe: schema-driven web-config** (retitle + re-field existing Draft card)
- Not a new card — repurpose existing AG-8.
- Retitle: "AG-8: `emhass init` Setup-Wizard CLI" → **"AG-8: Schema-driven web-config form
  + validation"**.
- Re-field: Phase `Phase 5` → `Phase 3`, Priority `P3` → `P2`, Category stays
  `B: End-User-Ops` (user-facing UI), Scope `Upstream`. Status stays `Ideas` (sequenced
  after schema spine: AC-2b + AM-2 + T6).
- Rewrite body: generate the config form + client/server validation from
  `param_definitions.json` (the same SoT that feeds AM-2 docs and T6 validation),
  replacing the flat config page. Member of the LLM-ready epic. Depends on AC-2b/AM-2/T6.
- Implementation note: retitle needs the `title` arg on `updateProjectV2DraftIssue`;
  `lib.update_draft_body` only sends `body` today → extend it (or add `update_draft`) to
  also set title.

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

1. `board/2026-06-04-reconcile-cuts.py` — move 4 cards to Won't Do (guarded by
   expected-status), de-reference AC-8 from AG-4/AG-9 via `append_to_body_idempotent` or
   a targeted body rewrite.
2. `board/2026-06-04-reconcile-adds.py` — create 3 goal-epic draft cards (LLM-ready,
   EV-EVCC, Reliability) + 2 work-item draft cards (B5 smoke-gate, B6 AGENTS.md, via
   `add_draft_to_project`) + set their fields; add 5 #875 issues/PRs as linked content
   (`addProjectV2ItemById`) + set Phase/Scope/Status; **reframe AG-8** (B7: retitle +
   re-field Phase/Priority + body rewrite). Title-existence guard before each draft
   create (idempotency).
   - Requires a `lib.py` tweak: extend `update_draft_body` (or add `update_draft`) to also
     set the draft `title` (for the AG-8 retitle).
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
- Read-back: confirm 4 cards in Won't Do; 3 epics + 2 work-item cards (smoke-gate,
  AGENTS.md) + 5 #875 cards present with correct fields; AG-8 retitled + re-fielded to
  Phase 3 / P2 (LLM-ready member); AM-7 grouped under Reliability; AC-8 de-referenced
  from AG-4/AG-9 bodies.
- `board/next.py` still runs clean (no schema break in items.json).
- `git diff board/design.md` review before commit.

## Out of Scope

- Sibling RFCs (priority/template/MQTT), public EV-demand example — gated on #931
  resonance, not carded now.
- **T5 EVCC resonance-accelerator** (small public worked-example to actively create
  resonance if #931 stalls) — NOT carded; stays an internal strategy note. Revisit if
  #931 goes quiet.
- Ensemble/BATNA private glue layer — never on the public board.
- GitHub Phase-field option mutation — not needed.
- Any upstream code change — this is board + doc curation only.
