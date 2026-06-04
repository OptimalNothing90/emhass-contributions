# Board ↔ Strategy Reconcile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `davidusb-geek/projects/2` in line with current strategy — cut 4 speculative cards, add 3 goal-epics + 2 work-items + 5 #875 regression cards, reframe AG-8, drop stale phase dates.

**Architecture:** Dated board-mutation Python scripts under `board/`, each importing `board/lib.py` helpers (gh-graphql wrapper, field setter, draft creator). Live board is the source of truth; `items.json` is the offline mirror reconciled by `fetch.py`. Every mutation is followed by `fetch.py` + a `--dry-run` 0-drift check + a git commit. Runs on `main` (board bookkeeping convention — all prior `board/2026-*.py` scripts commit on main, no worktree).

**Tech Stack:** Python 3 (stdlib only), `gh` CLI GraphQL, GitHub Projects v2 API.

**Spec:** `docs/superpowers/specs/2026-06-04-board-strategy-reconcile-design.md`

---

## Critical execution facts (read before any task)

- **Account:** `gh auth status` must show `OptimalNothing90` active. If not: `gh auth switch --user OptimalNothing90`. Never switch back mid-run.
- **Board id derivation** (`fetch.py:derive_id_from_title`): a draft card's `id` = the title prefix before the first `:` (regex `[A-Za-z][\w.-]*?`). New epics therefore need **distinct** prefixes (chosen: `EPIC-LLM`, `EPIC-EVCC`, `EPIC-REL`, `REL-1`, `REL-2` — all verified free against current `items.json`). Linked Issues/PRs auto-key as `PR-<n>`/`ISSUE-<n>` from the content number regardless of title.
- **Create scripts do NOT write `items.json`** — they mutate live only; `items.json` catches up on the next `python fetch.py`. (Status-move scripts via `set_field`+`save_items` DO write `items.json`.) Either way, after every script run: `python fetch.py` then commit.
- **Project ID:** `PVT_kwHOAfZrVs4BV1jU`.
- **Field/option ids:** read from `items.json["_meta"]["field_ids"]` and `["option_ids"]` at runtime — do NOT hardcode. Exact option keys: Status `Ideas|Candidates|Todo|In Progress|Review|Done / Wont Do` (note: "Wont" no apostrophe), Category `A: Code-Lifecycle|B: End-User-Ops|Infra`, Phase `Phase 0|Phase 1|Phase 1.5|Phase 2|Phase 3|Phase 4|Phase 5`, Priority `P0..P3`, Effort `XS|S|M|L|XL`, Scope `Upstream|Local|Discussion-Only`.

---

## File Structure

- `board/lib.py` — **modify**: add `update_draft_title_body()` (retitle needs the `title` arg; current `update_draft_body` sends body only).
- `tests/test_board_lib.py` — **create**: offline test for the new helper (monkeypatch `lib.gh`).
- `board/2026-06-04-reconcile-cuts.py` — **create**: 4 cards → `Done / Wont Do`; de-reference AC-8 from AG-4 body.
- `board/2026-06-04-reconcile-epics.py` — **create**: 5 draft cards (3 epics + REL-1 + REL-2) with id-freedom asserts + field sets.
- `board/2026-06-04-reconcile-linked-875.py` — **create**: add #933/#934/#938/#935/#936 as linked content + set fields.
- `board/2026-06-04-reconcile-ag8.py` — **create**: AG-8 retitle + body rewrite + re-field.
- `board/design.md` — **modify**: §5 phase targets (drop dates, re-theme Phase 4), strip stale EV-1..7 framing.

---

## Task 0: Pre-flight sync

**Files:** `board/items.json`

- [ ] **Step 1: Confirm account**

Run: `gh auth status`
Expected: `OptimalNothing90 ... Active account: true`. If not, `gh auth switch --user OptimalNothing90`.

- [ ] **Step 2: Refresh items.json from live**

Run: `cd board && python fetch.py`
Expected: drift report prints; `items.json` rewritten. Review `git diff board/items.json`.

- [ ] **Step 3: Commit the sync (only if changed)**

```bash
git add board/items.json
git commit -m "chore(board): pre-reconcile sync items.json with live"
```
(If `git diff --cached --quiet` shows nothing staged, skip the commit.)

---

## Task 1: lib helper for draft retitle

**Files:**
- Modify: `board/lib.py` (add after `update_draft_body`, ~line 81)
- Test: `tests/test_board_lib.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_board_lib.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "board"))
import lib  # noqa: E402


def test_update_draft_title_body_sends_both(monkeypatch):
    captured = {}

    def fake_gh(args, stdin=None):
        captured["args"] = args
        return json.dumps(
            {"data": {"updateProjectV2DraftIssue": {"draftIssue": {"id": "DI_x", "title": "New"}}}}
        )

    monkeypatch.setattr(lib, "gh", fake_gh)
    title = lib.update_draft_title_body("DI_x", "New", "Body text")
    assert title == "New"
    joined = " ".join(captured["args"])
    assert "title=New" in joined
    assert "body=Body text" in joined
    assert "DI_x" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions && python -m pytest tests/test_board_lib.py -v`
Expected: FAIL — `AttributeError: module 'lib' has no attribute 'update_draft_title_body'`.

- [ ] **Step 3: Implement the helper**

Add to `board/lib.py` after `update_draft_body` (the function ending at ~line 81):

```python
def update_draft_title_body(draft_id: str, title: str, body: str) -> str:
    """Set both title and body of a draft issue. Returns the new title."""
    q = """mutation($id: ID!, $title: String!, $body: String!) {
      updateProjectV2DraftIssue(input: { draftIssueId: $id, title: $title, body: $body }) {
        draftIssue { id title }
      }
    }"""
    out = gh_graphql(q, variables={"id": draft_id, "title": title, "body": body})
    return out["data"]["updateProjectV2DraftIssue"]["draftIssue"]["title"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_lib.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add board/lib.py tests/test_board_lib.py
git commit -m "feat(board): add update_draft_title_body lib helper"
```

---

## Task 2: Cuts → Won't Do + AC-8 de-reference

**Files:** Create `board/2026-06-04-reconcile-cuts.py`

- [ ] **Step 1: Write the script**

```python
"""Reconcile cuts (2026-06-04): move 4 speculative cards to Done / Wont Do and
de-reference the cut AC-8 from AG-4's body.

Per spec docs/superpowers/specs/2026-06-04-board-strategy-reconcile-design.md §A.
AG-9 is NOT touched here — it has no AC-8 reference (only AG-4 does). AG-9, CE-7,
AM-4, AM-5 are kept (not cut).
"""

from lib import (
    fetch_live_draft,
    find_item,
    load_items,
    save_items,
    set_field,
    update_draft_body,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# (board_id, expected_current_status)
CUTS = [
    ("AM-6", "Ideas"),
    ("AM-3", "Ideas"),
    ("AG-5", "Ideas"),
    ("AC-8", "Ideas"),
]

AC8_CLAUSE = " Demos value of structured error catalog (AC-8)."
AC8_REPLACEMENT = " Inline hints, standalone (no external error catalog)."


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    wontdo = option_ids["Status"]["Done / Wont Do"]

    for board_id, expected in CUTS:
        item = find_item(data, board_id)
        if item["Status"] != expected:
            print(f"SKIP {board_id}: status {item['Status']!r}, expected {expected!r}")
            continue
        set_field(PROJECT_ID, item["item_id"], field_ids["Status"], wontdo)
        item["Status"] = "Done / Wont Do"
        print(f"{board_id}: {expected} -> Done / Wont Do")

    # De-reference AC-8 from AG-4 (fetch live body first; idempotent on the clause)
    ag4 = find_item(data, "AG-4")
    live = fetch_live_draft(ag4["draft_id"])
    body = live.get("body") or ""
    if AC8_CLAUSE in body:
        new_body = body.replace(AC8_CLAUSE, AC8_REPLACEMENT)
        update_draft_body(ag4["draft_id"], new_body)
        ag4["body"] = new_body
        print("AG-4: de-referenced AC-8")
    else:
        print("AG-4: AC-8 clause not present (already de-referenced?) — skip")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `cd board && python 2026-06-04-reconcile-cuts.py`
Expected output: four `X: Ideas -> Done / Wont Do` lines + `AG-4: de-referenced AC-8` + `=== Done ===`. Any `SKIP` line means the live status drifted — stop and investigate before continuing.

- [ ] **Step 3: Verify live matches mirror**

Run: `python fetch.py --dry-run`
Expected: `no drift — items.json matches live` / `0 changed`.

- [ ] **Step 4: Read-back the cuts**

Run:
```bash
python -c "import json; d=json.load(open('items.json',encoding='utf-8')); by={i['id']:i for i in d['items']}; print({k:by[k]['Status'] for k in ['AM-6','AM-3','AG-5','AC-8']})"
```
Expected: all four show `Done / Wont Do`.

- [ ] **Step 5: Commit**

```bash
cd ..
git add board/2026-06-04-reconcile-cuts.py board/items.json
git commit -m "chore(board): cut 4 speculative cards to Wont Do + de-ref AC-8 from AG-4"
```

---

## Task 3: Create 3 epics + 2 work-items

**Files:** Create `board/2026-06-04-reconcile-epics.py`

- [ ] **Step 1: Write the script**

```python
"""Reconcile adds (2026-06-04): 3 goal-epics + 2 reliability work-items.

Per spec §B1/B2/B4/B5/B6. Create-only: items.json catches up on next fetch.py.
ids derived from title prefix before ':' — all asserted free first.
"""

from lib import add_draft_to_project, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# id, title, body, fields
CARDS = [
    (
        "EPIC-LLM",
        "EPIC-LLM: LLM-ready — machine-readable EMHASS",
        """\
Strategic goal epic. Make EMHASS machine-readable for coding agents + LLM consumers,
framed as **single schema -> many generated surfaces** (`param_definitions.json` = SoT).

Member items: AC-2 / AC-2c (schema), AM-1 / AM-1b (openapi), AM-2 (config.md docs),
AG-8 (schema-driven config UI), plus future llms.txt and runtime config-validation
(Pydantic/jsonschema of merged config -> clear errors; attacks the #869 null-default class).

Done-criterion: schema spine published + openapi runtime payloads + config.md auto-generated
+ config validated at load + config form schema-driven, with no drift between them.
""",
        {"Status": "In Progress", "Category": "A: Code-Lifecycle", "Phase": "Phase 3",
         "Priority": "P1", "Effort": "L", "Scope": "Discussion-Only"},
    ),
    (
        "EPIC-EVCC",
        "EPIC-EVCC: EV-EVCC integration — shared-plan registry",
        """\
Strategic goal epic. EMHASS = whole-house planner, evcc = executor; coordinated via a
stateful shared-plan registry (RFC 0001, posted as Discussion #931, awaiting community/
David resonance).

Member items: EV-9 (cookbook NR/MQTT/EVCC recipe), CE-7 (GUI EV-section).

Downstream (sibling RFCs, public worked-example) is gated on #931 resonance and is not
carded yet. Done-criterion: a recommend-only plan-exchange contract that evcc can consume,
accepted in EMHASS-core or shipped as an agreed integration surface.
""",
        {"Status": "In Progress", "Category": "B: End-User-Ops", "Phase": "Phase 4",
         "Priority": "P1", "Effort": "XL", "Scope": "Discussion-Only"},
    ),
    (
        "EPIC-REL",
        "EPIC-REL: Reliability / regression-harness",
        """\
Strategic goal epic. Reliability is the floor under both other goals; the v0.17.x
contributor wave + our own #830 -> #875 regression show happy-path-only changes reach
production.

Pillars:
1. Optim feasibility smoke-gate (REL-1) — would have caught #875 (hybrid infeasible) + #869.
2. Schema drift-guard — AM-7 (param_definitions <-> config_defaults).
3. Battery-MILP constraint correctness — refs #875 / #935 / #936 / ISSUE-807-U-2 (SoC-clamp,
   set_nodischarge_to_grid, dynamic charge-power all cluster in the battery constraint set).
4. Forecast-fetch resilience — refs U-3 / U-5 / U-6 (consistent timeout/retry/fallback
   across all forecast.py providers).
""",
        {"Status": "In Progress", "Category": "Infra", "Phase": "Phase 3",
         "Priority": "P1", "Effort": "XL", "Scope": "Discussion-Only"},
    ),
    (
        "REL-1",
        "REL-1: Optim feasibility smoke-gate (CI)",
        """\
Flagship of EPIC-REL. A CI job that runs a full optimization over a small matrix of
reference configs (incl. hybrid + battery) and asserts the run is feasible and key outputs
are within sane bounds. Catches the regression class of #875 (hybrid infeasible) and #869.
Can ride alongside AM-7. Issue-first, then PR.
""",
        {"Status": "Candidates", "Category": "A: Code-Lifecycle", "Phase": "Phase 3",
         "Priority": "P1", "Effort": "M", "Scope": "Upstream"},
    ),
    (
        "REL-2",
        "REL-2: AGENTS.md enforcement tightening",
        """\
Make `check_def_loads` mandatory + add a vanilla-optim-smoke reference in AGENTS.md;
honor-system -> enforced. **Gated on #886 + #900 landing** so AGENTS.md can point at real
enforcement. Card exists for visibility only until then (Status Ideas, do not promote).
""",
        {"Status": "Ideas", "Category": "A: Code-Lifecycle", "Phase": "Phase 3",
         "Priority": "P2", "Effort": "S", "Scope": "Upstream"},
    ),
]


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    existing_ids = {i["id"] for i in data["items"]}

    for board_id, title, body, fields in CARDS:
        if board_id in existing_ids:
            print(f"SKIP {board_id}: id already exists — would collide, not creating")
            continue
        item_id, draft_id = add_draft_to_project(PROJECT_ID, title, body)
        print(f"created {board_id}: item={item_id} draft={draft_id}")
        for fname, val in fields.items():
            set_field(PROJECT_ID, item_id, field_ids[fname], option_ids[fname][val])
        print(f"  fields set: {fields}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `cd board && python 2026-06-04-reconcile-epics.py`
Expected: five `created <id>` blocks, no `SKIP`. A `SKIP ... would collide` line means the id is taken — stop and pick a new free id before re-running.

- [ ] **Step 3: Ingest + verify ids**

Run: `python fetch.py`
Expected drift: five `[NEW]` lines keyed exactly `EPIC-LLM`, `EPIC-EVCC`, `EPIC-REL`, `REL-1`, `REL-2`. If any `[NEW]` shows a different id (e.g. `EPIC`), the title prefix parsed wrong — investigate before committing.

- [ ] **Step 4: Read-back fields**

Run:
```bash
python -c "import json; d=json.load(open('items.json',encoding='utf-8')); by={i['id']:i for i in d['items']}; [print(k, by[k]['Status'], by[k]['Category'], by[k]['Phase'], by[k]['Priority']) for k in ['EPIC-LLM','EPIC-EVCC','EPIC-REL','REL-1','REL-2']]"
```
Expected: matches the field sets in the script (e.g. `EPIC-LLM In Progress A: Code-Lifecycle Phase 3 P1`).

- [ ] **Step 5: Commit**

```bash
cd ..
git add board/2026-06-04-reconcile-epics.py board/items.json
git commit -m "feat(board): add 3 goal-epics (LLM-ready, EV-EVCC, Reliability) + 2 work-items"
```

---

## Task 4: Add #875 regression cards (linked content)

**Files:** Create `board/2026-06-04-reconcile-linked-875.py`

- [ ] **Step 1: Write the script**

```python
"""Reconcile adds (2026-06-04): add the #875 regression-cluster PRs/issues as linked
project content + set triage fields. Per spec §B3.

#933/#934/#938 are PRs; #935/#936 are issues. addProjectV2ItemById is idempotent per
(project, content) so re-running is safe. items.json catches up on next fetch.py;
fetch keys these as PR-<n> / ISSUE-<n> automatically.
"""

from lib import add_content_to_project, gh, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
REPO = "davidusb-geek/emhass"

# number, kind ('pr'|'issue'), board status
TARGETS = [
    (933, "pr", "In Progress"),
    (934, "pr", "In Progress"),
    (938, "pr", "In Progress"),
    (935, "issue", "Candidates"),
    (936, "issue", "Candidates"),
]
COMMON = {"Phase": "Phase 2", "Scope": "Upstream"}


def node_id(number: int, kind: str) -> str:
    sub = "pr" if kind == "pr" else "issue"
    out = gh([sub, "view", str(number), "--repo", REPO, "--json", "id", "-q", ".id"])
    return out.strip()


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    for number, kind, status in TARGETS:
        cid = node_id(number, kind)
        item_id = add_content_to_project(PROJECT_ID, cid)
        print(f"#{number} ({kind}): content={cid} item={item_id}")
        fields = {**COMMON, "Status": status}
        for fname, val in fields.items():
            set_field(PROJECT_ID, item_id, field_ids[fname], option_ids[fname][val])
        print(f"  fields: {fields}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `cd board && python 2026-06-04-reconcile-linked-875.py`
Expected: five `#<n> (...): content=... item=...` lines + field lines. If `gh pr view`/`gh issue view` errors (wrong kind for a number), fix the `TARGETS` kind and re-run (idempotent).

- [ ] **Step 3: Ingest + verify**

Run: `python fetch.py`
Expected: `[NEW]` lines keyed `PR-933`, `PR-934`, `PR-938`, `ISSUE-935`, `ISSUE-936`.

- [ ] **Step 4: Read-back fields**

Run:
```bash
python -c "import json; d=json.load(open('items.json',encoding='utf-8')); by={i['id']:i for i in d['items']}; [print(k, by[k]['Status'], by[k]['Phase'], by[k]['Scope']) for k in ['PR-933','PR-934','PR-938','ISSUE-935','ISSUE-936']]"
```
Expected: each `... Phase 2 Upstream`, statuses `In Progress`×3 then `Candidates`×2.

- [ ] **Step 5: Commit**

```bash
cd ..
git add board/2026-06-04-reconcile-linked-875.py board/items.json
git commit -m "feat(board): card #875 regression cluster (#933/#934/#938/#935/#936)"
```

---

## Task 5: AG-8 reframe (retitle + re-field)

**Files:** Create `board/2026-06-04-reconcile-ag8.py`

- [ ] **Step 1: Write the script**

```python
"""Reconcile (2026-06-04): reframe AG-8 from CLI Setup-Wizard to schema-driven web-config.

Per spec §B7. Title prefix stays 'AG-8' so the board id does not re-key. Changes:
title, body, Phase 5->3, Priority P3->P2. Category (B), Scope (Upstream), Effort (L),
Status (Ideas) unchanged.
"""

from lib import find_item, load_items, save_items, set_field, update_draft_title_body

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

NEW_TITLE = "AG-8: Schema-driven web-config form + validation"
NEW_BODY = """\
Generate the EMHASS config form + client/server validation from
`param_definitions.json` — the same SoT that feeds AM-2 (config.md docs) and the
runtime config-validation work. Replaces the flat config page; one schema drives
docs + validation + UI (LLM-ready: single schema -> many surfaces).

Member of the LLM-ready epic (EPIC-LLM). Depends on AC-2b (runtime params in schema),
AM-2, and the config-validation deliverable. Supersedes the original `emhass init`
CLI-wizard framing (a CLI wizard duplicated the existing web config page).
"""

REFIELD = {"Phase": "Phase 3", "Priority": "P2"}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    ag8 = find_item(data, "AG-8")
    if ag8["Phase"] != "Phase 5":
        print(f"WARN AG-8 Phase is {ag8['Phase']!r}, expected 'Phase 5' — continuing")

    update_draft_title_body(ag8["draft_id"], NEW_TITLE, NEW_BODY)
    ag8["title"] = NEW_TITLE
    ag8["body"] = NEW_BODY
    print(f"AG-8 retitled -> {NEW_TITLE!r}")

    for fname, val in REFIELD.items():
        set_field(PROJECT_ID, ag8["item_id"], field_ids[fname], option_ids[fname][val])
        ag8[fname] = val
        print(f"  set {fname} = {val}")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `cd board && python 2026-06-04-reconcile-ag8.py`
Expected: `AG-8 retitled -> ...` + `set Phase = Phase 3` + `set Priority = P2` + `=== Done ===`.

- [ ] **Step 3: Verify live matches mirror + id unchanged**

Run: `python fetch.py --dry-run`
Expected: `0 changed`, `0 new`. Critically NO `[NEW] AG-8...` and NO `[GONE] AG-8` (id must stay `AG-8`; a NEW/GONE pair means the prefix re-keyed — investigate).

- [ ] **Step 4: Read-back**

Run:
```bash
python -c "import json; d=json.load(open('items.json',encoding='utf-8')); a=[i for i in d['items'] if i['id']=='AG-8'][0]; print(a['title']); print(a['Phase'], a['Priority'], a['Category'], a['Scope'], a['Status'])"
```
Expected: new title; `Phase 3 P2 B: End-User-Ops Upstream Ideas`.

- [ ] **Step 5: Commit**

```bash
cd ..
git add board/2026-06-04-reconcile-ag8.py board/items.json
git commit -m "refactor(board): reframe AG-8 CLI-wizard -> schema-driven web-config"
```

---

## Task 6: design.md phase re-baseline

**Files:** Modify `board/design.md`

- [ ] **Step 1: Locate stale EV-1..7 / local-coupling references**

Run: `cd board && grep -n "EV-1\|EV-Coupling\|EV-7\|Target" design.md`
Expected: hits in §5 (Phase Targets table) and the Phase 4/5 rows. Note line numbers.

- [ ] **Step 2: Replace the Phase Targets table**

Replace the block beginning `### Phase Targets (aspirational)` and its table (the `| Phase | Theme | Target | Notes |` table through the `Phase 5` row) with:

```markdown
### Phase Themes (sequencing only — date targets retired 2026-06-04)

> Date targets were aspirational and all elapsed; Phase is now a pure cross-repo
> sequencing field with no calendar. Themes below are descriptive.

| Phase | Theme | Notes |
|-------|-------|-------|
| Phase 0 | Local Sanity | shipped (CE-1, CE-3, AG-1) |
| Phase 1 | Upstream Quick-Wins | shipped (#812/#813/#817/#814/#816/#822/#829) |
| Phase 1.5 | Workflow-Demo + AGENTS.md | board itself is the demo (#808) |
| Phase 2 | Bug-Klärung + regression cluster | U-1/U-8 issue-first; #875 cards #933/#934/#938/#935/#936 |
| Phase 3 | Schema/API + LLM-ready + Reliability | EPIC-LLM, EPIC-REL, AC-2*, AM-1*, AM-2, AM-7, REL-1/REL-2, AG-8 |
| Phase 4 | EVCC Integration | EPIC-EVCC (RFC 0001 / #931), EV-9, CE-7 — EMHASS planner / evcc executor |
| Phase 5 | Long-form (thinned 2026-06-04) | AG-9, AM-4, AG-pr-readiness, AG-B1 (AM-6/AM-3/AG-5/AC-8 cut to Won't Do) |
```

- [ ] **Step 3: Fix the §1 goal / scope-corridor wording if it names local EV coupling**

Run: `grep -n "EV-Coupling\|EVCC/HA\|hardware/glue" design.md`
For any line still framing Phase 4 as "EV-Coupling (local)" or implying EMHASS does the coupling, leave the #789 corridor statements intact (EMHASS = MILP optimiser; evcc/HA = separate tools) — that framing is still correct post-pivot. Only edit a line if it literally says "EV-Coupling (local)" as the Phase 4 theme; replace with "EVCC Integration". If no such line outside the table, no change needed here.

- [ ] **Step 4: Verify the doc still renders sanely**

Run: `grep -n "Phase 4 | EVCC Integration\|date targets retired" design.md`
Expected: both present. Confirm no remaining `EV-1..7` references: `grep -n "EV-1\b\|EV-2\b\|EV-7\b" design.md` → no output.

- [ ] **Step 5: Commit**

```bash
cd ..
git add board/design.md
git commit -m "docs(board): retire phase date-targets, re-theme Phase 4 -> EVCC Integration"
```

---

## Task 7: Final verification

**Files:** none (read-only checks)

- [ ] **Step 1: Picker still parses items.json**

Run: `cd board && python next.py --limit 5 --scope both`
Expected: runs without traceback; lists Todo items (AG-2 + the 5 promoted earlier). REL-1 (Candidates) and epics (In Progress) correctly do NOT appear in quick-wins.

- [ ] **Step 2: Full live-vs-mirror parity**

Run: `python fetch.py --dry-run`
Expected: `no drift — items.json matches live`, `0 new, 0 removed, 0 changed`.

- [ ] **Step 3: Reconcile read-back summary**

Run:
```bash
python -c "import json; d=json.load(open('items.json',encoding='utf-8')); st={};
[st.setdefault(i['Status'],[]).append(i['id']) for i in d['items']];
print('Wont Do contains AM-6/AM-3/AG-5/AC-8:', all(x in st.get('Done / Wont Do',[]) for x in ['AM-6','AM-3','AG-5','AC-8']));
ids={i['id'] for i in d['items']};
print('new cards present:', all(x in ids for x in ['EPIC-LLM','EPIC-EVCC','EPIC-REL','REL-1','REL-2','PR-933','PR-934','PR-938','ISSUE-935','ISSUE-936']))"
```
Expected: both `True`.

- [ ] **Step 4: Update the resume-point memory**

Update `project_state_snapshot_2026-06-03.md` (or write a `2026-06-04` successor) noting: board reconciled — 4 cuts to Won't Do, 3 epics + REL-1/REL-2 + 5 #875 cards added, AG-8 reframed, phase dates retired. Add the one-line pointer in `MEMORY.md`. (Memory lives at the auto-memory path, not in the repo.)

---

## Self-Review (completed during planning)

- **Spec coverage:** §A cuts → Task 2; AG-8 reframe (§A note + §B7) → Task 5; §B1/B2/B4/B5/B6 → Task 3; §B3 → Task 4; §C → Task 6; lib title-arg note (§Components) → Task 1. All covered.
- **Spec correction folded in:** spec §A said de-ref AC-8 from AG-4 **and** AG-9; only AG-4 actually references AC-8, so Task 2 de-refs AG-4 only. (Update the spec's wording opportunistically.)
- **Placeholder scan:** no TBD/TODO; every script is complete runnable code; every command has expected output.
- **Type/name consistency:** `update_draft_title_body` defined in Task 1, used in Task 5. Field/option keys match the verified `_meta` option strings ("Done / Wont Do", "Phase 3", etc.). Chosen ids (EPIC-LLM/EPIC-EVCC/EPIC-REL/REL-1/REL-2) verified absent from current `items.json`.
```
