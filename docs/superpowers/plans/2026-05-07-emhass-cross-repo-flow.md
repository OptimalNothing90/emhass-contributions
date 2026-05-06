# emhass-cross-repo-flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode the emhass cross-repo contribution loop as two new Claude-Code skills (`emhass-next-item-picker`, `emhass-cross-repo-flow`) plus one Python picker script (`board/next.py`) with full pytest coverage, and extend the existing `emhass-board-merge-bookkeeping` skill to handle closed-not-merged PRs.

**Architecture:** Meta-tooling lives entirely in `OptimalNothing90/emhass-contributions`. `board/next.py` is a pure-stdlib Python script (no GitHub API calls; reads `board/items.json`) that filters and ranks board items, with two output formats (md + json). The picker skill is a thin conversational wrapper over the script. The cross-repo-flow skill orchestrates routing assessment → spec/plan generation (delegating bodies to `superpowers:brainstorming` + `superpowers:writing-plans`) → handoff-prompt assembly → board status updates → pivot pathways. The handoff-prompt sends the user to a sibling Claude Code session in `claude-code/emhass/` (the fork) for actual upstream code work — no auto-handoff, no marker-file IPC. Templates live as `.md.tpl` files separate from skill bodies for independent edit cycles. The bookkeeping skill grows by ~30 lines for the closed-not-merged path; merge path stays as-is.

**Tech Stack:** Python 3.11+ (stdlib only; no new deps), pytest (already in dev workflow via pre-commit), ruff + ruff-format (pre-commit), `gh` CLI (skill bodies only — never from the script), Markdown + YAML frontmatter for skills, plain string templating for `.md.tpl` files.

**Source spec:** `docs/superpowers/specs/2026-05-07-emhass-cross-repo-flow-design.md` (read end-to-end before executing this plan).

**Memory entries that drive content:**
- `feedback_no_auto_bugfix.md` — bug default-skip
- `feedback_pr_first_for_strategic.md` — PR-first for strategic items
- `feedback_branch_naming.md` — deterministic branch naming
- `project_strategic_goals.md` — LLM-ready + EV-EVCC goal streams

---

## File Structure

| Path | Responsibility | New / Modified |
|---|---|---|
| `board/next.py` | Picker script: filter + rank + render. Stdlib only. | New |
| `tests/__init__.py` | Empty marker (so pytest discovers `tests/`). | New |
| `tests/fixtures/items_sample.json` | Hand-curated mini items.json (~15 items) covering every filter/ranking edge case. | New |
| `tests/test_board_next.py` | 14 unit tests per spec §13.1. | New |
| `.pre-commit-config.yaml` | Add local pytest hook running `pytest tests/test_board_next.py`. | Modified |
| `.claude/skills/emhass-cross-repo-flow/SKILL.md` | Main orchestration skill body. | New |
| `.claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl` | Plan-light spec template (§9). | New |
| `.claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl` | Handoff prompt template (§10). | New |
| `.claude/skills/emhass-next-item-picker/SKILL.md` | Picker wrapper skill body. | New |
| `.claude/skills/emhass-board-merge-bookkeeping/SKILL.md` | Description + closed-not-merged section appended. Merge-path logic unchanged. | Modified |
| `docs/superpowers/plans/2026-05-07-emhass-cross-repo-flow.md` | This plan. | Existing (you are reading it) |

The plan touches **no** upstream emhass code, **no** items.json schema, and **no** existing `board/` script bodies (`fetch.py`, `lib.py`, `extend.py`, etc.).

---

## Task 1: Pre-flight verification

**Goal:** Confirm working state matches plan assumptions before any edit.

**Files:** none (read-only).

- [ ] **Step 1: Confirm working directory + repo**

```bash
pwd
git rev-parse --show-toplevel
```

Expected: `C:/Users/MauricioSchäpers/claude-code/emhass-contributions` for both.

- [ ] **Step 2: Confirm GitHub account is `OptimalNothing90`**

```bash
gh auth status
```

Expected: line `Active account: true` under `OptimalNothing90`. If `mschaepers` is active, run:

```bash
gh auth switch --user OptimalNothing90
```

Re-run `gh auth status` to confirm.

- [ ] **Step 3: Confirm clean tree on `main`**

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: `nothing to commit, working tree clean` and branch is `main`.

- [ ] **Step 4: Create implementation branch**

Per `feedback_branch_naming.md`, deterministic name. This work is meta-tooling for THIS repo (not upstream), so the slug is descriptive of the feature, no board-id required:

```bash
git checkout -b chore/cross-repo-flow
git status
```

Expected: clean tree on new branch.

- [ ] **Step 5: Confirm spec and reference plan exist**

```bash
test -f docs/superpowers/specs/2026-05-07-emhass-cross-repo-flow-design.md && echo SPEC_OK || echo SPEC_MISSING
test -f docs/superpowers/plans/2026-04-30-ag-7-agents-md.md && echo REF_OK || echo REF_MISSING
test -f .claude/skills/emhass-board-merge-bookkeeping/SKILL.md && echo BOOK_OK || echo BOOK_MISSING
```

Expected: all three print the `_OK` form.

No commit at end of Task 1.

---

## Task 2: Create test scaffolding directory + empty marker

**Goal:** Create the `tests/` tree pytest will discover, with the empty `__init__.py` marker. No actual tests yet; that comes in Task 4.

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep` (placeholder so the directory commits)

- [ ] **Step 1: Create directories**

```bash
mkdir -p tests/fixtures
```

- [ ] **Step 2: Write `tests/__init__.py`**

Empty file:

```bash
: > tests/__init__.py
```

- [ ] **Step 3: Verify pytest sees the empty tree**

```bash
python -m pytest tests/ -q
```

Expected: `no tests ran in 0.0Xs` exit 5 (no tests collected) — that is fine; we'll add the test file in Task 4.

- [ ] **Step 4: Commit scaffolding**

```bash
git add tests/__init__.py tests/fixtures/
git commit -m "chore(tests): add empty tests/ scaffolding for board picker"
```

---

## Task 3: Create test fixture `items_sample.json`

**Goal:** Hand-curated mini items.json covering every filter rule and sort scenario from §8 + §13.1. The fixture must be self-contained — picker tests load it via path, not via `board/items.json`.

**Files:**
- Create: `tests/fixtures/items_sample.json`

Edge cases the fixture must exercise (mapping to the 14 unit tests):

| Item id | Type | Status | Phase | Pri | Effort | Scope | Goal | Body marker | labels | Purpose |
|---|---|---|---|---|---|---|---|---|---|---|
| `DRAFT-DONE` | draft | Done / Wont Do | Phase 1 | P1 | S | Upstream | LLM-ready | — | — | excluded by Status filter |
| `DRAFT-IN-PROGRESS` | draft | In Progress | Phase 1 | P1 | S | Upstream | LLM-ready | — | — | excluded by Status filter |
| `DRAFT-REVIEW` | draft | Review | Phase 1 | P1 | S | Upstream | — | — | — | excluded by Status filter |
| `DRAFT-PR-PENDING` | draft | Todo | Phase 1 | P1 | S | Upstream | — | — | — | sibling-PR test target (excluded because of `LINK-PR-REVIEW` below) |
| `LINK-PR-REVIEW` | link | Review | Phase 1 | P1 | S | Upstream | — | — | — | sibling of `DRAFT-PR-PENDING` (`linked_to: DRAFT-PR-PENDING`) |
| `ISSUE-BUG` | link | Todo | Phase 1 | P1 | S | Upstream | — | — | `["bug","triage"]` | bug-label default-skip; included with `--include-bugs` |
| `DRAFT-BLOCKED` | draft | Todo | Phase 1 | P1 | S | Upstream | — | `Blocked-by: DRAFT-DONE-BLOCKER` (and a sibling `DRAFT-DONE-BLOCKER` is **not** Done — Status=Todo — so blocker not done → filtered) | — | blocked-by filter |
| `DRAFT-DONE-BLOCKER` | draft | Todo | Phase 1 | P3 | M | Upstream | — | — | — | the named blocker (kept Todo so the filter sees blocker not Done) |
| `AC-3` | draft | Todo | Phase 1 | P1 | XS | Upstream | — | `linked #999` | — | quick-win + AC prefix → goal-fit fallback `LLM-ready`; sort top |
| `EV-7` | draft | Todo | Phase 3 | P0 | M | Upstream | EV-EVCC | — | — | strategic; not quick-win (Effort=M) |
| `AG-99` | draft | Todo | Phase 1 | P2 | S | Upstream | — | — | — | quick-win but not strategic (Pri=P2) |
| `INF-1` | draft | Todo | Phase 0 | P3 | XS | Upstream | — | — | — | quick-win, no goal-fit (no field, prefix not AC/EV) |
| `LOCAL-1` | draft | Todo | Phase 1 | P1 | S | Local | — | — | — | excluded when `--scope=upstream` (default) |
| `BOTH-1` | draft | Todo | Phase 1 | P1 | S | Discussion-Only | — | — | — | excluded when `--scope=upstream` |
| `GOAL-FIELD` | draft | Todo | Phase 1 | P1 | S | Upstream | LLM-ready | — | — | Goal field present → tag = LLM-ready (overrides prefix; prefix=GOAL would be empty) |

Note on schema: `linked_to` is a new picker-only field on link items, used only by the sibling-PR-Review filter; `labels` is an optional list field on link items, absent on draft items. Neither is required by the live `items.json`; the fixture introduces them so the picker can be tested without GitHub API calls.

- [ ] **Step 1: Write the fixture file**

```bash
cat > tests/fixtures/items_sample.json <<'EOF'
{
  "_meta": {
    "spec_version": "1.1-test",
    "date": "2026-05-07",
    "project_id": "PVT_TEST",
    "field_ids": {},
    "option_ids": {}
  },
  "items": [
    {
      "id": "DRAFT-DONE",
      "title": "Already done item",
      "type": "draft",
      "body": "",
      "Status": "Done / Wont Do",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream",
      "Goal": "LLM-ready"
    },
    {
      "id": "DRAFT-IN-PROGRESS",
      "title": "In flight item",
      "type": "draft",
      "body": "",
      "Status": "In Progress",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream",
      "Goal": "LLM-ready"
    },
    {
      "id": "DRAFT-REVIEW",
      "title": "Review item",
      "type": "draft",
      "body": "",
      "Status": "Review",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream"
    },
    {
      "id": "DRAFT-PR-PENDING",
      "title": "Draft awaiting sibling PR review",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream"
    },
    {
      "id": "LINK-PR-REVIEW",
      "title": "Sibling PR in review",
      "type": "link",
      "linked_to": "DRAFT-PR-PENDING",
      "Status": "Review",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream",
      "repository": "davidusb-geek/emhass",
      "number": 800,
      "labels": []
    },
    {
      "id": "ISSUE-BUG",
      "title": "An upstream bug",
      "type": "link",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream",
      "repository": "davidusb-geek/emhass",
      "number": 343,
      "labels": ["bug", "triage"]
    },
    {
      "id": "DRAFT-BLOCKED",
      "title": "Blocked draft",
      "type": "draft",
      "body": "Blocked-by: DRAFT-DONE-BLOCKER",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream"
    },
    {
      "id": "DRAFT-DONE-BLOCKER",
      "title": "Blocker still open",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P3",
      "Effort": "M",
      "Scope": "Upstream"
    },
    {
      "id": "AC-3",
      "title": "AC-3 stub item",
      "type": "draft",
      "body": "linked #999",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "XS",
      "Scope": "Upstream"
    },
    {
      "id": "EV-7",
      "title": "EV-7 strategic item",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 3",
      "Priority": "P0",
      "Effort": "M",
      "Scope": "Upstream",
      "Goal": "EV-EVCC"
    },
    {
      "id": "AG-99",
      "title": "AG-99 medium-priority quick win",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P2",
      "Effort": "S",
      "Scope": "Upstream"
    },
    {
      "id": "INF-1",
      "title": "Infra prefix, no goal-fit",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "Infra",
      "Phase": "Phase 0",
      "Priority": "P3",
      "Effort": "XS",
      "Scope": "Upstream"
    },
    {
      "id": "LOCAL-1",
      "title": "Local-only item",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "B: End-User-Ops",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Local"
    },
    {
      "id": "BOTH-1",
      "title": "Discussion-only item",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Discussion-Only"
    },
    {
      "id": "GOAL-FIELD",
      "title": "Item with explicit Goal field",
      "type": "draft",
      "body": "",
      "Status": "Todo",
      "Category": "A: Code-Lifecycle",
      "Phase": "Phase 1",
      "Priority": "P1",
      "Effort": "S",
      "Scope": "Upstream",
      "Goal": "LLM-ready"
    }
  ]
}
EOF
```

- [ ] **Step 2: Validate JSON**

```bash
python -c "import json,sys; json.load(open('tests/fixtures/items_sample.json',encoding='utf-8')); print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/items_sample.json
git commit -m "test(board): add items_sample.json fixture for picker tests"
```

---

## Task 4: Skeleton `board/next.py` + first failing test

**Goal:** TDD red-green for the smallest unit: a `load_items(path)` helper and a `filter_status_todo(items)` function. Subsequent tasks layer on top.

**Files:**
- Create: `board/next.py`
- Create: `tests/test_board_next.py`

- [ ] **Step 1: Write the failing test**

```bash
cat > tests/test_board_next.py <<'EOF'
"""Unit tests for board/next.py picker logic.

Tests load tests/fixtures/items_sample.json and exercise individual
filter / ranking / rendering functions. No GitHub API, no live items.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "board"))

import next as picker  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "items_sample.json"


@pytest.fixture
def items() -> list[dict]:
    return picker.load_items(FIXTURE)["items"]


def test_filter_excludes_done_items(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    ids = {it["id"] for it in out}
    assert "DRAFT-DONE" not in ids
EOF
```

- [ ] **Step 2: Run test, expect failure**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: `ModuleNotFoundError: No module named 'next'` (or import error). That confirms the test runs and the module is missing.

- [ ] **Step 3: Write minimal `board/next.py`**

```bash
cat > board/next.py <<'EOF'
"""Pick next emhass board items for upstream PR work.

Reads board/items.json (or a passed path), applies filters per design
spec §8, and emits two ranked candidate lists (Quick-Win + Strategic).

Pure stdlib. No GitHub API calls. No side effects beyond writing to
stdout. Skill wrappers (emhass-next-item-picker, emhass-cross-repo-flow)
are responsible for conversational presentation and live-API behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_ITEMS = Path(__file__).parent / "items.json"


def load_items(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def filter_candidates(
    items: list[dict],
    *,
    scope: str = "upstream",
    include_bugs: bool = False,
) -> list[dict]:
    """Apply all filter rules from spec §8.

    Returns items where: Status=Todo, Scope matches, no sibling PR in
    Review, no unresolved Blocked-by marker, no bug label (unless flag).
    """
    return [it for it in items if it.get("Status") == "Todo"]


if __name__ == "__main__":
    raise SystemExit("CLI not yet wired; later task adds argparse + render.")
EOF
```

- [ ] **Step 4: Run test, expect pass**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: `test_filter_excludes_done_items PASSED`.

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): add next.py skeleton with Status=Todo filter"
```

---

## Task 5: Add Status / sibling-PR / Blocked-by / Scope filters (tests 2-6)

**Goal:** Extend `filter_candidates` to cover all six filter rules. Five new tests (cumulative 6 of 14).

**Files:**
- Modify: `tests/test_board_next.py`
- Modify: `board/next.py`

- [ ] **Step 1: Append five tests to `tests/test_board_next.py`**

Append after the existing `test_filter_excludes_done_items`:

```python
def test_filter_excludes_in_progress(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    ids = {it["id"] for it in out}
    assert "DRAFT-IN-PROGRESS" not in ids
    assert "DRAFT-REVIEW" not in ids


def test_filter_excludes_review_siblings(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    ids = {it["id"] for it in out}
    # DRAFT-PR-PENDING has sibling LINK-PR-REVIEW with Status=Review
    assert "DRAFT-PR-PENDING" not in ids


def test_filter_excludes_bug_label_default(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    ids = {it["id"] for it in out}
    assert "ISSUE-BUG" not in ids


def test_filter_includes_bug_label_with_flag(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=True)
    ids = {it["id"] for it in out}
    assert "ISSUE-BUG" in ids


def test_filter_blocked_by_marker(items):
    out = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    ids = {it["id"] for it in out}
    # DRAFT-BLOCKED has Blocked-by: DRAFT-DONE-BLOCKER which is not Done
    assert "DRAFT-BLOCKED" not in ids
    # DRAFT-DONE-BLOCKER itself is plain Todo, not blocked, should remain
    assert "DRAFT-DONE-BLOCKER" in ids
```

- [ ] **Step 2: Run; expect five new failures**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: `test_filter_excludes_in_progress PASSED` (already covered by Status=Todo); other four FAIL.

- [ ] **Step 3: Replace `filter_candidates` in `board/next.py`**

Replace the body of `filter_candidates` with the full filter chain. Edit the function only; leave imports and `load_items` in place.

```python
import re

BLOCKED_RE = re.compile(r"^\s*Blocked-by:\s*([A-Za-z0-9_-]+)", re.MULTILINE)


def _scope_matches(item: dict, scope: str) -> bool:
    if scope == "both":
        return True
    item_scope = (item.get("Scope") or "").lower()
    return item_scope == scope


def _has_sibling_in_review(item: dict, all_items: list[dict]) -> bool:
    return any(
        sib.get("type") == "link"
        and sib.get("linked_to") == item["id"]
        and sib.get("Status") == "Review"
        for sib in all_items
    )


def _is_blocked(item: dict, all_items: list[dict]) -> bool:
    body = item.get("body") or ""
    m = BLOCKED_RE.search(body)
    if not m:
        return False
    blocker_id = m.group(1)
    blocker = next((b for b in all_items if b.get("id") == blocker_id), None)
    if blocker is None:
        return False
    return blocker.get("Status") != "Done / Wont Do"


def _has_bug_label(item: dict) -> bool:
    return "bug" in (item.get("labels") or [])


def filter_candidates(
    items: list[dict],
    *,
    scope: str = "upstream",
    include_bugs: bool = False,
) -> list[dict]:
    out = []
    for it in items:
        if it.get("Status") != "Todo":
            continue
        if not _scope_matches(it, scope):
            continue
        if _has_sibling_in_review(it, items):
            continue
        if _is_blocked(it, items):
            continue
        if not include_bugs and _has_bug_label(it):
            continue
        out.append(it)
    return out
```

- [ ] **Step 4: Run; all six filter tests pass**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): add scope, sibling-PR, blocked-by, bug-label filters"
```

---

## Task 6: Quick-Win and Strategic ranking (tests 7-10)

**Goal:** Two ranked-list functions per spec §8.

- Quick-Win: pre-filter `Effort ∈ {XS, S}`, sort `Phase asc → Priority asc → Effort asc → id asc`.
- Strategic: pre-filter `Priority ∈ {P0, P1}`, sort `Priority asc → Phase asc → Effort asc → id asc`.

**Files:**
- Modify: `tests/test_board_next.py`
- Modify: `board/next.py`

- [ ] **Step 1: Append four tests**

```python
def test_quickwin_only_xs_s(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    qw = picker.rank_quickwin(cands)
    assert all(it["Effort"] in ("XS", "S") for it in qw)
    # EV-7 is M Effort → must be excluded
    assert "EV-7" not in {it["id"] for it in qw}


def test_strategic_only_p0_p1(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    st = picker.rank_strategic(cands)
    assert all(it["Priority"] in ("P0", "P1") for it in st)
    assert "AG-99" not in {it["id"] for it in st}  # P2


def test_quickwin_sort_order(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    qw = picker.rank_quickwin(cands)
    ids = [it["id"] for it in qw]
    # AC-3 (Phase 1, P1, XS) before AG-99 (Phase 1, P2, S)
    # INF-1 (Phase 0, P3, XS) before AC-3 because Phase 0 < Phase 1
    assert ids.index("INF-1") < ids.index("AC-3") < ids.index("AG-99")


def test_strategic_sort_order(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    st = picker.rank_strategic(cands)
    ids = [it["id"] for it in st]
    # EV-7 is P0 → must come before any P1 item
    p0_idx = ids.index("EV-7")
    for p1_id in ("AC-3", "GOAL-FIELD", "DRAFT-DONE-BLOCKER"):
        if p1_id in ids:
            assert p0_idx < ids.index(p1_id)
```

- [ ] **Step 2: Run; expect four AttributeError failures**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: `AttributeError: module 'next' has no attribute 'rank_quickwin'` (and similar).

- [ ] **Step 3: Append ranking helpers to `board/next.py`** (after `filter_candidates`)

```python
PHASE_ORDER = {
    "Phase 0": 0, "Phase 1": 1, "Phase 1.5": 2,
    "Phase 2": 3, "Phase 3": 4, "Phase 4": 5, "Phase 5": 6,
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
EFFORT_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4}


def _phase_rank(item: dict) -> int:
    return PHASE_ORDER.get(item.get("Phase", ""), 99)


def _priority_rank(item: dict) -> int:
    return PRIORITY_ORDER.get(item.get("Priority", ""), 99)


def _effort_rank(item: dict) -> int:
    return EFFORT_ORDER.get(item.get("Effort", ""), 99)


def rank_quickwin(items: list[dict]) -> list[dict]:
    pre = [it for it in items if it.get("Effort") in ("XS", "S")]
    return sorted(
        pre,
        key=lambda it: (
            _phase_rank(it),
            _priority_rank(it),
            _effort_rank(it),
            it.get("id", ""),
        ),
    )


def rank_strategic(items: list[dict]) -> list[dict]:
    pre = [it for it in items if it.get("Priority") in ("P0", "P1")]
    return sorted(
        pre,
        key=lambda it: (
            _priority_rank(it),
            _phase_rank(it),
            _effort_rank(it),
            it.get("id", ""),
        ),
    )
```

- [ ] **Step 4: Run; all 10 tests pass**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): add quick-win and strategic ranking with tests"
```

---

## Task 7: Goal-fit derivation (tests 11-12)

**Goal:** Derive a goal-fit tag for each item per spec §8: (i) `Goal` field if present; (ii) ID-prefix heuristic (`AC-*` → `LLM-ready`, `EV-*` → `EV-EVCC`); (iii) empty string.

**Files:**
- Modify: `tests/test_board_next.py`
- Modify: `board/next.py`

- [ ] **Step 1: Append two tests**

```python
def test_goal_fit_field_wins(items):
    item = next(it for it in items if it["id"] == "GOAL-FIELD")
    assert picker.goal_fit(item) == "LLM-ready"


def test_goal_fit_prefix_fallback(items):
    ac = next(it for it in items if it["id"] == "AC-3")
    ev = next(it for it in items if it["id"] == "EV-7")
    inf = next(it for it in items if it["id"] == "INF-1")
    assert picker.goal_fit(ac) == "LLM-ready"
    assert picker.goal_fit(ev) == "EV-EVCC"
    assert picker.goal_fit(inf) == ""
```

Note: `EV-7` has explicit `Goal: EV-EVCC` in the fixture; the assertion still passes because (i) returns `EV-EVCC` regardless of prefix. This also implicitly verifies that the field-vs-prefix precedence is correct.

- [ ] **Step 2: Run; expect failure**

```bash
python -m pytest tests/test_board_next.py -v -k goal
```

Expected: `AttributeError: module 'next' has no attribute 'goal_fit'`.

- [ ] **Step 3: Add `goal_fit` to `board/next.py`** (after the rank functions)

```python
GOAL_PREFIX_MAP = {
    "AC": "LLM-ready",
    "EV": "EV-EVCC",
}


def goal_fit(item: dict) -> str:
    g = item.get("Goal")
    if g:
        return g
    item_id = item.get("id", "")
    prefix = item_id.split("-", 1)[0] if "-" in item_id else item_id
    return GOAL_PREFIX_MAP.get(prefix, "")
```

- [ ] **Step 4: Run; tests pass**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): derive goal-fit from Goal field then ID prefix"
```

---

## Task 8: Why-Quick / Why-Strategic templates + Markdown render

**Goal:** Deterministic per-row "why" string + a `render_markdown(quickwins, strategics, today)` function. Per spec §8 the rationale comes from item fields/body markers, never from an LLM.

The "why-quick" template covers, in priority order:
1. `linked #N` if body contains `linked #<digits>` → `linked #N, <effort> effort`
2. `Goal=<value>` if goal-fit non-empty → `<value>, <effort> effort`
3. fallback → `<effort> effort, Phase {phase}`

The "why-strategic" template:
1. Goal-fit non-empty → `goal-fit: <value>, Phase {phase}`
2. fallback → `Phase {phase} / {priority}`

**Files:**
- Modify: `tests/test_board_next.py`
- Modify: `board/next.py`

- [ ] **Step 1: Append rendering tests (cumulative 13/14)**

```python
def test_empty_lists_render_placeholder():
    md = picker.render_markdown([], [], today="2026-05-07")
    assert "(no items match these criteria)" in md
    assert "# Next emhass items — 2026-05-07" in md


def test_render_markdown_includes_goalfit_column(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    qw = picker.rank_quickwin(cands)[:3]
    st = picker.rank_strategic(cands)[:3]
    md = picker.render_markdown(qw, st, today="2026-05-07")
    assert "Quick wins" in md
    assert "Strategic next" in md
    assert "Goal-fit" in md
```

- [ ] **Step 2: Run; expect failure**

```bash
python -m pytest tests/test_board_next.py -v -k render
```

Expected: `AttributeError: module 'next' has no attribute 'render_markdown'`.

- [ ] **Step 3: Append render helpers to `board/next.py`**

```python
LINKED_RE = re.compile(r"linked\s+#(\d+)", re.IGNORECASE)
EMPTY_PLACEHOLDER = "_(no items match these criteria)_"


def why_quick(item: dict) -> str:
    body = item.get("body") or ""
    m = LINKED_RE.search(body)
    effort = item.get("Effort", "")
    if m:
        return f"linked #{m.group(1)}, {effort} effort"
    g = goal_fit(item)
    if g:
        return f"{g}, {effort} effort"
    return f"{effort} effort, {item.get('Phase', '')}"


def why_strategic(item: dict) -> str:
    g = goal_fit(item)
    phase = item.get("Phase", "")
    if g:
        return f"goal-fit: {g}, {phase}"
    return f"{phase} / {item.get('Priority', '')}"


def _row(item: dict, why: str) -> str:
    return (
        f"| {item.get('id','')} | {goal_fit(item)} | {item.get('title','')} | "
        f"{item.get('Phase','')} | {item.get('Priority','')} | "
        f"{item.get('Effort','')} | {why} |"
    )


def render_markdown(
    quickwins: list[dict],
    strategics: list[dict],
    *,
    today: str,
) -> str:
    parts = [f"# Next emhass items — {today}", ""]

    parts.append("## Quick wins (Effort XS/S, Todo, no block)")
    parts.append("")
    parts.append("| ID | Goal-fit | Title | Phase | Pri | Effort | Why quick |")
    parts.append("|----|----------|-------|-------|-----|--------|-----------|")
    if quickwins:
        for it in quickwins:
            parts.append(_row(it, why_quick(it)))
    else:
        parts.append(EMPTY_PLACEHOLDER)
    parts.append("")

    parts.append("## Strategic next (P0/P1, lowest Phase)")
    parts.append("")
    parts.append("| ID | Goal-fit | Title | Phase | Pri | Effort | Why strategic |")
    parts.append("|----|----------|-------|-------|-----|--------|---------------|")
    if strategics:
        for it in strategics:
            parts.append(_row(it, why_strategic(it)))
    else:
        parts.append(EMPTY_PLACEHOLDER)

    return "\n".join(parts)
```

- [ ] **Step 4: Run; tests pass**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: 14 passed (the test count is now 14 — note that `test_render_markdown_includes_goalfit_column` is auxiliary and the count stays aligned with §13.1 because we have not yet added the JSON test).

Wait — the spec lists 14 *required* tests. Re-count: 6 filter + 4 ranking + 2 goal-fit + 1 empty-placeholder + 1 json-schema = 14. The auxiliary `test_render_markdown_includes_goalfit_column` makes 15 actual tests. Acceptable; spec acceptance criteria is "all 14 unit tests pass" — the extra is not a violation. Mark mentally as "14 spec-required tests + 1 sanity check". The 14th spec test (`test_json_output_schema`) lands in Task 9.

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): add why-templates and markdown rendering"
```

---

## Task 9: JSON output (test 14)

**Goal:** `--format=json` output: a structure with `date`, `quickwins`, `strategics`. Each list contains `{id, title, phase, priority, effort, scope, goal_fit, why}`.

**Files:**
- Modify: `tests/test_board_next.py`
- Modify: `board/next.py`

- [ ] **Step 1: Append the spec's 14th required test**

```python
def test_json_output_schema(items):
    cands = picker.filter_candidates(items, scope="upstream", include_bugs=False)
    qw = picker.rank_quickwin(cands)
    st = picker.rank_strategic(cands)
    payload = picker.render_json(qw, st, today="2026-05-07")
    parsed = json.loads(payload)
    assert parsed["date"] == "2026-05-07"
    assert isinstance(parsed["quickwins"], list)
    assert isinstance(parsed["strategics"], list)
    if parsed["quickwins"]:
        sample = parsed["quickwins"][0]
        for key in ("id", "title", "phase", "priority", "effort",
                    "scope", "goal_fit", "why"):
            assert key in sample, f"missing key: {key}"
```

- [ ] **Step 2: Run; expect failure**

```bash
python -m pytest tests/test_board_next.py -v -k json
```

Expected: `AttributeError: module 'next' has no attribute 'render_json'`.

- [ ] **Step 3: Add `render_json` to `board/next.py`**

```python
def _json_entry(item: dict, why: str) -> dict:
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "phase": item.get("Phase", ""),
        "priority": item.get("Priority", ""),
        "effort": item.get("Effort", ""),
        "scope": item.get("Scope", ""),
        "goal_fit": goal_fit(item),
        "why": why,
    }


def render_json(
    quickwins: list[dict],
    strategics: list[dict],
    *,
    today: str,
) -> str:
    payload = {
        "date": today,
        "quickwins": [_json_entry(it, why_quick(it)) for it in quickwins],
        "strategics": [_json_entry(it, why_strategic(it)) for it in strategics],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: all 15 pass (14 spec-required + 1 markdown sanity).

- [ ] **Step 5: Commit**

```bash
git add board/next.py tests/test_board_next.py
git commit -m "feat(board): add json output mode for picker"
```

---

## Task 10: Wire CLI (`__main__`) per spec §8

**Goal:** Replace the Task-4 placeholder `__main__` with an argparse CLI matching spec §8.

**Files:**
- Modify: `board/next.py`

- [ ] **Step 1: Replace the `__main__` block in `board/next.py`**

Find the block:

```python
if __name__ == "__main__":
    raise SystemExit("CLI not yet wired; later task adds argparse + render.")
```

Replace with:

```python
def main(argv: list[str] | None = None) -> int:
    import datetime as _dt

    p = argparse.ArgumentParser(
        prog="board/next.py",
        description="Pick next emhass board items (Quick-Win + Strategic).",
    )
    p.add_argument("--mode", choices=("quickwin", "strategic", "both"),
                   default="both")
    p.add_argument("--include-bugs", action="store_true")
    p.add_argument("--scope", choices=("upstream", "local", "both"),
                   default="upstream")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--format", choices=("md", "json"), default="md")
    p.add_argument("--items", type=Path, default=DEFAULT_ITEMS,
                   help="Path to items.json (default: board/items.json)")
    p.add_argument("--today", default=None,
                   help="Override date string (YYYY-MM-DD); default: today.")
    args = p.parse_args(argv)

    today = args.today or _dt.date.today().isoformat()
    data = load_items(args.items)
    items = data["items"]
    cands = filter_candidates(
        items, scope=args.scope, include_bugs=args.include_bugs,
    )

    qw = rank_quickwin(cands)[: args.limit] if args.mode in ("quickwin", "both") else []
    st = rank_strategic(cands)[: args.limit] if args.mode in ("strategic", "both") else []

    # Edge case: everything in flight (no Todo items at all matched filters)
    if args.format == "md" and not qw and not st:
        msg = (
            f"# Next emhass items — {today}\n\n"
            "_Picker empty — everything in flight, wait for merges._\n"
        )
        sys.stdout.write(msg)
        return 0

    if args.format == "json":
        sys.stdout.write(render_json(qw, st, today=today) + "\n")
    else:
        sys.stdout.write(render_markdown(qw, st, today=today) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test against the live items.json**

```bash
python board/next.py --limit 3
python board/next.py --limit 3 --format json
python board/next.py --mode quickwin --limit 5
python board/next.py --include-bugs --limit 2
```

Expected: each produces non-empty output without traceback. Eyeball: the markdown has both sections, the JSON parses, `--include-bugs` does not change the live output if no bug-labelled link items exist in `board/items.json` (currently no `labels` field in live data → bug filter is a no-op live).

- [ ] **Step 3: Run pytest one more time**

```bash
python -m pytest tests/test_board_next.py -v
```

Expected: all tests still pass (no regression).

- [ ] **Step 4: Run ruff**

```bash
python -m ruff check board/next.py tests/test_board_next.py
python -m ruff format --check board/next.py tests/test_board_next.py
```

If format-check fails, run `python -m ruff format board/next.py tests/test_board_next.py` and re-run pytest.

- [ ] **Step 5: Commit**

```bash
git add board/next.py
git commit -m "feat(board): wire next.py CLI per spec §8"
```

---

## Task 11: Pre-commit hook for picker tests

**Goal:** Add a local pre-commit hook that runs `pytest tests/test_board_next.py` so picker regressions are caught before commit.

**Files:**
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Append a local hook**

Add this block at the end of `.pre-commit-config.yaml` (after the existing `scrub-private-refs` hook, still inside the same `repo: local` block — append a new hook entry):

```yaml
      - id: pytest-board-next
        name: pytest tests/test_board_next.py
        entry: python -m pytest tests/test_board_next.py -q
        language: system
        # only run when the picker script or its tests / fixture change
        files: ^(board/next\.py|tests/(test_board_next\.py|fixtures/items_sample\.json))$
        pass_filenames: false
```

Open `.pre-commit-config.yaml` and append the hook under the existing `- repo: local` → `hooks:` list. The final structure:

```yaml
  - repo: local
    hooks:
      - id: scrub-private-refs
        name: Scrub private-repo / personal account refs
        entry: python scripts/scrub-private-refs.py
        language: system
        types: [text]
        exclude: '^(upstream/|scripts/scrub-private-refs\.py$)'
      - id: pytest-board-next
        name: pytest tests/test_board_next.py
        entry: python -m pytest tests/test_board_next.py -q
        language: system
        files: ^(board/next\.py|tests/(test_board_next\.py|fixtures/items_sample\.json))$
        pass_filenames: false
```

- [ ] **Step 2: Validate yaml**

```bash
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml',encoding='utf-8')); print('OK')"
```

Expected: `OK`. (PyYAML is a pre-commit transitive dep; if missing in the user's env, install with `pip install pyyaml` first or skip this validation.)

- [ ] **Step 3: Trigger the hook on a no-op edit**

```bash
pre-commit run pytest-board-next --files board/next.py
```

Expected: `pytest tests/test_board_next.py.....Passed`. If `pre-commit` is not installed, install with `pip install pre-commit` then `pre-commit install` first.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore(pre-commit): run pytest tests/test_board_next.py"
```

---

## Task 12: Spec template `spec.md.tpl`

**Goal:** Plan-light spec template per spec §9. Skill performs simple `{{placeholder}}` string replace; no templating engine.

**Files:**
- Create: `.claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl`

- [ ] **Step 1: Create the directory + write the template**

```bash
mkdir -p .claude/skills/emhass-cross-repo-flow/templates
cat > .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl <<'EOF'
# {{board_id}} — {{title}} — Design

**Date:** {{date}}
**Card:** `{{board_id}}` (board/items.json)
**Issue:** {{issue_link_or_none}}
**Audit source:** {{audit_path_or_none}}
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Branch:** `{{branch_name}}`
**Effort:** {{effort}}
**Phase / Priority:** {{phase}} / {{priority}}
**Goal-fit:** {{goal_fit}}

## 1. Problem

{{problem_paragraph}}

## 2. Goal

{{goal_sentence}}

## 3. Decisions

| # | Decision | Source |
|---|----------|--------|
{{decision_rows}}

## 4. Files touched

{{files_touched_list}}

## 5. Concrete edits

{{concrete_edits_table}}

## 6. Test strategy

{{test_strategy_paragraph}}

## 7. Acceptance criteria

{{acceptance_bullets}}

## 8. Out of scope

{{out_of_scope_or_none}}

## 9. References

- Issue: {{issue_link_or_none}}
- Audit: {{audit_path_or_none}}
- Memory: {{memory_refs_or_none}}
EOF
```

- [ ] **Step 2: Verify file exists and contains expected placeholders**

```bash
test -f .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl
grep -c '{{' .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl
```

Expected: file exists; placeholder count >= 18.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl
git commit -m "feat(skill): add plan-light spec template for cross-repo-flow"
```

---

## Task 13: Handoff-prompt template `handoff-prompt.md.tpl`

**Goal:** Verbatim copy of spec §10 template content. Lives separately so handoff-prompt edits do not require touching SKILL.md logic.

**Files:**
- Create: `.claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl`

- [ ] **Step 1: Write the template**

```bash
cat > .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl <<'TEMPLATE_EOF'
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
````

After Fork-Session reports HANDOFF-RESULT, return to the main planning session and paste
the result block. Main session will:
- On `pr-open`: update Board-Card to `Status: Review`
- On `blocked`: read appended Pivot Reason, re-plan
- On `failed`: triage, decide
TEMPLATE_EOF
```

Note: outer here-doc terminator is `TEMPLATE_EOF` because the template body itself contains a literal `EOF` (in the PR-body here-doc) and a literal triple-backtick block. Outer delimiter must be unique.

- [ ] **Step 2: Verify file exists with placeholders**

```bash
test -f .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl
grep -c '{{' .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl
```

Expected: file exists; placeholder count >= 12.

- [ ] **Step 3: Sanity-check that the template produced is a valid Markdown** (no syntax surprises)

```bash
head -5 .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl
tail -5 .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl
```

Expected: starts with `## Handoff-Prompt`, ends with `- On 'failed': triage, decide`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl
git commit -m "feat(skill): add handoff-prompt template for cross-repo-flow"
```

---

## Task 14: `emhass-next-item-picker` SKILL.md

**Goal:** Wrapper skill that invokes `board/next.py` and presents output. Style mirrors `emhass-board-merge-bookkeeping` (frontmatter description, Pre-flight, decisions, Self-test PENDING marker).

**Files:**
- Create: `.claude/skills/emhass-next-item-picker/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p .claude/skills/emhass-next-item-picker
```

- [ ] **Step 2: Write the SKILL.md**

```bash
cat > .claude/skills/emhass-next-item-picker/SKILL.md <<'SKILL_EOF'
---
name: emhass-next-item-picker
description: Use when the user wants to identify the next emhass board item to work on. Triggers on phrases like "was kommt als nächstes", "what's next", "what should I work on", "quick wins", "schnelle Sachen", "strategic next", "großes Item next", "show me the board", "zeig was offen ist", or as the chained tail of `emhass-cross-repo-flow` after PR merge bookkeeping. Does NOT fire when the user has already named a concrete item; in that case route to `emhass-cross-repo-flow` directly.
---

# EMHASS Next-Item Picker

Surfaces ranked candidate board items for the next contribution. Wraps `board/next.py`
(deterministic filter + rank, stdlib only, no GitHub API). This skill is the
conversational presentation layer; all selection logic lives in the script and is
covered by `tests/test_board_next.py`.

## Self-test (one-shot, at first use after this skill was authored)

**STATUS: PENDING.**

On first use after authoring, run:

```bash
python board/next.py --limit 3
python board/next.py --limit 3 --format json
python board/next.py --limit 3   # second run, must produce identical output (modulo date header)
```

Pass criteria:
- Both Markdown outputs identical except for the `# Next emhass items — YYYY-MM-DD` header line
- JSON output validates as JSON (`python -c "import json,sys; json.load(sys.stdin)"`)
- No bug-labelled link item appears in the default-mode output (verify by reading `board/items.json` for any link item with `labels: ["bug", ...]` — there are none today, so this is a no-op proof; once such an item exists, the proof becomes meaningful)

After STATUS: DONE, this section is audit trail only. Do not re-run.

## When to fire

Fires on:
- "Was kommt als nächstes?" / "what's next" / "what should I work on?"
- "Quick wins?" / "schnelle Sachen?"
- "Strategic next" / "großes Item next"
- "Show me the board" / "zeig was offen ist"
- Halbautomatic chained call from `emhass-cross-repo-flow` end ("pick next item? (j/n)")

Does NOT fire on:
- User already named a concrete item — go straight to `emhass-cross-repo-flow`
- "Liste mir alle bugs" — picker default-filters bugs; user wants the live `gh issue list` instead

## Pre-flight (always, in order)

1. **Working directory** — must be at repo root (`C:/Users/MauricioSchäpers/claude-code/emhass-contributions`). Verify with `git rev-parse --show-toplevel`.
2. **No auth needed** — picker is read-only stdlib, never touches `gh`. Skip `gh auth status`.
3. **items.json freshness check** — optional but recommended once per session: `cd board && python fetch.py --dry-run`. If drift > 0, ask user whether to run `python fetch.py` for real before picking. Stale items.json can hide just-merged items as still `Review`.

## Invocation pattern

Default — show both lists, top 5 each:

```bash
python board/next.py --limit 5
```

User intent shorthand mapping:

| User says | Flags |
|---|---|
| "Quick wins?" | `--mode quickwin --limit 5` |
| "Strategic" / "großes Item" | `--mode strategic --limit 5` |
| "include bugs" / "auch goodwill bugs" | `--include-bugs` (after explicit user opt-in per `feedback_no_auto_bugfix`) |
| "local items auch" | `--scope both` |
| "json please" | `--format json` |

## Goal-fit annotation

The script already tags each row with goal-fit (`LLM-ready`, `EV-EVCC`, or empty). Do NOT
re-annotate or LLM-paraphrase. Show the script output verbatim.

Per `project_strategic_goals.md`, the two strategic threads are LLM-ready and EV-EVCC.
Items with empty goal-fit are infra/hygiene — surface them but mention "non-goal" so the
user can deprioritise fast.

## Bug-label discipline

Per `feedback_no_auto_bugfix`: bug-labelled upstream issues are default-skipped. Surface
them only when the user explicitly says "auch bugs", "goodwill bug", or names a specific
bug as personally relevant (e.g. "I have a battery, fix #343"). If user asks "any quick
wins?" without bug-context, do NOT pre-emptively offer bug-labelled items.

## Hand-off to `emhass-cross-repo-flow`

After presenting picker output, ask: "Item picken? (ID nennen) oder abbrechen?"

When the user names an item:
- If item has `Scope: Upstream` → invoke `emhass-cross-repo-flow` skill with the item id
- If item has `Scope: Local` → out of scope for cross-repo-flow (Type 2/3); ask user
  whether to drop into ad-hoc planning instead
- If user says "abbrechen" / "stop" → exit, no state change

## What this skill does NOT do

- Implementation, planning, brainstorming — those are `emhass-cross-repo-flow`'s job
- Item content reasoning — picker output is the only signal; do not LLM-summarise items
- GitHub API calls — script is offline; freshness via `fetch.py`, not live queries
- Mutation of `items.json` — read-only

## Common mistakes

| Mistake | Reality |
|---|---|
| Skipping picker, asking LLM "what should I do next?" | `board/next.py` is the source of truth; LLM ranking drifts and double-counts |
| Re-paraphrasing the picker table | Loses determinism; use script output verbatim |
| Suggesting bug-labelled items by default | Violates `feedback_no_auto_bugfix`; require explicit user opt-in |
| Inventing item IDs | If user types an ID not in `items.json`, ask `find_item` to confirm before routing |
SKILL_EOF
```

- [ ] **Step 3: Verify frontmatter and STATUS marker**

```bash
head -3 .claude/skills/emhass-next-item-picker/SKILL.md
grep -n "STATUS: PENDING" .claude/skills/emhass-next-item-picker/SKILL.md
```

Expected: frontmatter line with `name: emhass-next-item-picker`; STATUS line found.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/emhass-next-item-picker/SKILL.md
git commit -m "feat(skill): add emhass-next-item-picker wrapper skill"
```

---

## Task 15: `emhass-cross-repo-flow` SKILL.md

**Goal:** The orchestration skill. Encodes routing assessment, spec/plan production, handoff-prompt assembly, board status updates, pivot pathways, and loop-end prompt. Reads `feedback_no_auto_bugfix`, `feedback_pr_first_for_strategic`, `feedback_branch_naming`, and `project_strategic_goals` as behavioural anchors.

This is the largest single file in the plan. Total length ~280-340 lines.

**Files:**
- Create: `.claude/skills/emhass-cross-repo-flow/SKILL.md`

- [ ] **Step 1: Create the file**

```bash
cat > .claude/skills/emhass-cross-repo-flow/SKILL.md <<'SKILL_EOF'
---
name: emhass-cross-repo-flow
description: Use when starting work on a Type-1 (upstream PR) emhass board item. Triggers on phrases like "lass uns AC-2a angehen", "let's do AG-7", "starten wir ag-b1", "issue #826 angehen", "PR für 824 vorbereiten", "auf goodwill #343 fixen", or generic "ich will PR machen für …" / "lass uns das nächste angehen" when item context is clear from prior turn. Orchestrates routing assessment → spec → plan → handoff-prompt → board status updates and chains into `emhass-board-merge-bookkeeping` on PR close (merged or not). Does NOT fire on Type-2 audits/RFCs, "what's next?" without item (that's the picker), or "write the bookkeeping script" (that's the bookkeeping skill).
---

# EMHASS Cross-Repo Flow

Orchestrates the multi-repo contribution loop:

```
items.json → routing → spec → plan → handoff-prompt → fork session → PR → bookkeeping → next item?
```

Scope: Type-1 items (`Scope=Upstream`). Type-2 (audit/RFC) and Type-3 (Local) items are
explicitly out of scope per spec Decision #6.

## Self-test (one-shot, at first use after this skill was authored)

**STATUS: PENDING.**

First live use after authoring runs the skill against AC-2a (board id `AC-2a`) per spec §13.2 / §13.3:

1. Routing-Assessment fires; item snapshot lists Phase 1, P1, Effort S, audit `audits/2026-04-28-param-definitions.md`, issue #826 open with no maintainer engagement.
2. Recommended path = `plan-light` (audit exists → reasoning documented).
3. Skill writes spec to `docs/superpowers/specs/2026-05-08-ac-2a-design.md` via `templates/spec.md.tpl`.
4. Skill invokes `superpowers:writing-plans` to produce `docs/superpowers/plans/2026-05-08-ac-2a.md`.
5. Skill appends `## Handoff-Prompt` section to the plan via `templates/handoff-prompt.md.tpl`.
6. Skill moves AC-2a board card `Status: Todo → In Progress`.
7. Skill prints handoff prompt to user but **stops before fork-session opens**. Branch is NOT created in the fork; PR is NOT opened.
8. After verification, the user reverts the board card to `Status: Todo` and (optionally) deletes the spec/plan files. Flip this STATUS marker to `DONE` with a one-line note documenting outcome (paths produced, any deviations).

Pass criteria:
- Spec exists at expected path
- Plan exists at expected path with `## Handoff-Prompt` section
- Handoff prompt contains the resolved `branch_name = feat/ac-2a-unit-field` (per `feedback_branch_naming`)
- Board card was moved to `In Progress` (visible in `items.json` after `fetch.py`)
- No fork-side commits, no upstream PR

After STATUS: DONE, this section is audit trail only.

## Pre-flight (always, in order)

1. **Auth** — `gh auth status`. Must show `OptimalNothing90` active. Switch with
   `gh auth switch --user OptimalNothing90` if not. Required for board mutations and
   issue lookups.
2. **Working directory** — `git rev-parse --show-toplevel` must equal the
   `emhass-contributions` repo path. This skill must NOT run in the fork repo.
3. **Tree state** — `git status` should be clean OR have only docs/superpowers edits in
   flight. Halt and ask if tree is dirty with non-docs changes.
4. **items.json freshness** — `cd board && python fetch.py --dry-run`. If drift, run
   `python fetch.py` and commit. Stale state misroutes (e.g. shows item as Todo when it's
   already In Progress upstream).
5. **Resume detection** — search `docs/superpowers/{specs,plans}/*.md` for files matching
   the board id. If found:
   - spec only, no plan → resume at writing-plans
   - spec + plan → check whether the plan has a `## Pivot Reason` section
     - if yes → re-plan path (see §Pivot)
     - if no → ask user: regenerate handoff or abort? (don't double-issue handoffs)

## Phase 1 — Routing-Mini-Assessment

Read item context (in order):

1. Board item from `board/items.json` (use `find_item` from `board/lib.py`).
2. Linked issue, if any: `gh issue view <N> --repo davidusb-geek/emhass --json title,body,labels,comments,author`.
3. Existing audit/RFC if body references one (`audits/...md`, `rfcs/...md`).
4. Existing spec/plan with same board id (already done in pre-flight Step 5).

Apply signal table (per spec §11):

| Signal | Implication |
|---|---|
| Bug-label on linked issue | **HARD-STOP.** Per `feedback_no_auto_bugfix`: ask "goodwill or eigen-betroffen?" before continuing. (a)/(b)/(c). User answer unlocks the rest of routing. |
| Existing audit/RFC | `plan-light` — reasoning already documented |
| Maintainer commented in last 14d with solution direction | `plan-light` — well-defined task |
| Maintainer linked PR as solution to issue | **HARD-STOP.** Item is in flight upstream; ask user before parallel-work |
| Goal-fit = EV-EVCC or LLM-ready, no audit/RFC | `brainstorm` — strategic, **PR-first** per `feedback_pr_first_for_strategic`. Skip RFC-first path. |
| Goal-fit = empty, no audit/RFC | `brainstorm` with "really worth doing?" check |
| Effort = XS, 1-3-line edit / doc typo | `direct` — handoff only, no spec/plan |

Present the routing-assessment to the user in the format from spec §11 ("sample output"
section). Always present the recommended path AND the alternatives (`brainstorm` /
`plan-light` / `direct` / `abbrechen`).

User-response handling:
- `"plan-light"` / `"go"` / `"empfohlen"` → proceed with recommended path
- `"brainstorm"` → invoke `superpowers:brainstorming` with pre-loaded context
- `"direct"` → handoff-prompt only, no spec/plan
- `"abbrechen"` / `"stop"` → exit; no board update
- A content question → answer, then re-ask the routing question

### Bug-label special case

Print the §11 "Bug special-case" template verbatim. User answers (a)/(b)/(c) before
routing continues. (a) and (b) unlock; (c) requires explicit reason.

### Strategic-item special case (PR-first)

Print the §11 "Strategic-item special-case" template verbatim. RFC-first only acceptable
if maintainer engaged on issue/discussion or open corridor-block exists.

## Phase 2 — Spec production

Path = `plan-light`:
- Read `templates/spec.md.tpl`, fill placeholders from item / issue / audit
- Write to `docs/superpowers/specs/{YYYY-MM-DD}-{board_id_lowercase}-design.md`
- The board id slugifies as: lowercase, replace spaces with `-` (e.g. `AC-2a` stays
  `ac-2a`; `EV-1` stays `ev-1`)

Path = `brainstorm`:
- Invoke `superpowers:brainstorming` skill with item context. Brainstorming writes the
  spec to `docs/superpowers/specs/...`. This skill does not reimplement.

Path = `direct`:
- No spec. Skip to Phase 4 (handoff only).

After spec exists, confirm path with user before invoking writing-plans.

## Phase 3 — Plan production

Invoke `superpowers:writing-plans` with the spec path. Writing-plans produces the plan
body in AG-7 style (Goal, Architecture, Tech Stack, File Structure, Tasks).

After plan body is written, append `## Handoff-Prompt` section by reading
`templates/handoff-prompt.md.tpl` and filling placeholders (see Phase 4).

Plan filename: `docs/superpowers/plans/{YYYY-MM-DD}-{board_id_lowercase}.md`.

## Phase 4 — Handoff-prompt assembly

Resolve branch name deterministically per `feedback_branch_naming`:

| Source | Pattern | Example |
|---|---|---|
| Board item with strategic feature | `feat/<board-id-lower>-<short-slug>` | `feat/ac-2a-unit-field` |
| Issue-driven bug fix | `fix/i<issue>-<short-slug>` | `fix/i343-batt-efficiency` |
| Documentation | `docs/<board-id-lower>` | `docs/ag-7` |
| Tooling / hygiene | `chore/<board-id-lower>` | `chore/board-tooling` |

The skill MUST resolve and emit the exact branch name in the handoff prompt. Never
"pick a good branch name yourself" — that drift violates `feedback_branch_naming`.

Fill `templates/handoff-prompt.md.tpl` placeholders:

| Placeholder | Source |
|---|---|
| `{{board_id}}` | item id from picker / user-named |
| `{{issue_link_or_none}}` | from item `content_url` if `type=link`; else `None` |
| `{{goal_fit}}` | `goal_fit(item)` from `board/next.py` (or repeat the rule inline) |
| `{{spec_relative_path}}` | computed in Phase 2 |
| `{{plan_relative_path}}` | computed in Phase 3 |
| `{{branch_name}}` | resolved per the table above |
| `{{pr_title}}` | from spec §1 / issue title; conventional commit prefix per branch type |
| `{{pr_body_skeleton}}` | spec sections 1+2+9 + issue link, no LLM padding |

Append the rendered template to the plan file as a new `## Handoff-Prompt` section.

## Phase 5 — Board card status update

After plan + handoff-prompt are written:

1. `cd board && python fetch.py` (refresh first — same hygiene as bookkeeping skill)
2. Author a one-shot script `board/{YYYY-MM-DD}-{board_id_lowercase}-start.py` that:
   - Imports `find_item, set_field` from `board/lib.py`
   - Sets `Status: Todo → In Progress` for the board card
   - Saves items.json
3. Run the script
4. `python fetch.py --dry-run` → must show 0 drift
5. Commit: `chore(board): start {board-id} ({YYYY-MM-DD})`

Reference structure (from `emhass-board-merge-bookkeeping` skill, adapted for status-only
mutation):

```python
from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
set_field(PROJECT_ID, item["item_id"],
          field_ids["Status"], option_ids["Status"]["In Progress"])
item["Status"] = "In Progress"
save_items(data)
```

## Phase 6 — Hand off to fork session

Show user the rendered handoff prompt block (the fenced code block from
`templates/handoff-prompt.md.tpl`) with all placeholders resolved. Tell them:

> "Open a NEW Claude Code session in `C:/Users/MauricioSchäpers/claude-code/emhass/`,
> paste the prompt above. Come back here with the `HANDOFF-RESULT` block when fork-session
> reports back."

Skill exits this phase. State is persisted in items.json + plan file. User decides
when to re-engage.

## Phase 7 — Receive HANDOFF-RESULT

When the user pastes back a `HANDOFF-RESULT <board_id>` block, parse the four fields:
`status`, `pr-url`, `branch`, `tests`, `notes`.

| status | Action |
|---|---|
| `pr-open` | Add PR sibling card via bookkeeping helpers (see spec §10's "On pr-open" path); set Board-Card to `Status: Review`; await maintainer |
| `blocked` | Read `## Pivot Reason` section from the plan file (fork-session appended it). Move to Pivot pathway (a) below |
| `failed` | Triage with user; do not auto-rollback. Could be auth issue, missing branch, gh CLI bug |

For `pr-open`: write a short script analogous to Phase-5's start script, but adding the
PR sibling card and moving Board-Card to `Review`. Use `add_content_to_project` from
`board/lib.py` (idempotent guard via `find_item`).

## Phase 8 — On PR close (chain into bookkeeping)

When the user reports the PR closed (merged or otherwise), invoke
`emhass-board-merge-bookkeeping` skill. That skill handles:
- Merge → standard bookkeeping (Case A or B)
- Closed-not-merged → won't-do mode (added by Task 16 of this plan)

Cross-repo-flow exits after delegating.

## Phase 9 — Loop-end prompt (halbautomatisch)

After bookkeeping completes (user confirms `STATUS: DONE`), ask:

> "Pick next item? (j/n)"

- `j` / `ja` / `yes` → invoke `emhass-next-item-picker`
- `n` / `nein` / `no` → exit, log nothing
- Anything else → ask once more, then default to `n`

This is the only auto-chain in the skill. Per spec Decision #7, never proceed without
explicit confirmation.

## Pivot pathways

### (a) Plan is wrong (fork-session-discovered)

Trigger: user pastes `HANDOFF-RESULT <id>` with `status: blocked`.

Actions:
1. `gh auth status` — confirm OptimalNothing90
2. Read the plan's `## Pivot Reason` section
3. Move Board-Card back to `Status: Todo` (no `Blocked` status exists in the project)
4. Present three options to user:
   - **Re-plan in place** — invoke `superpowers:writing-plans` again with updated context.
     Mark the old plan with `[SUPERSEDED-BY: <new-plan-path>]` at top; do not delete.
   - **Spec revision** — if divergence touches design assumptions, re-enter
     `superpowers:brainstorming` for that decision only. Append `## Revisions` to spec.
   - **Drop item** — upstream reality makes work irrelevant. Mark Won't Do via
     `emhass-board-merge-bookkeeping` (won't-do mode), document, exit.
5. User chooses → corresponding path

What does NOT happen:
- No auto-re-plan without explicit user confirmation
- No fork-side branch deletion (user manages)
- No bookkeeping invocation unless user picks "Drop item"

### (c) PR closed-not-merged

Trigger: `gh pr view <N> --repo davidusb-geek/emhass --json state,mergedAt` shows
`state=CLOSED, mergedAt=null`. User can also surface manually: "PR #N wurde geschlossen,
nicht gemerged".

Actions:
1. `gh auth status` — confirm OptimalNothing90
2. Read maintainer comments: `gh pr view <N> --repo davidusb-geek/emhass --comments`.
   Surface the most recent owner comment to user.
3. Present three options (per spec §12.c):
   - **Won't Do** — invoke `emhass-board-merge-bookkeeping` with won't-do mode flag
   - **Re-do with changes** — append `## Revisions` to spec; mark plan SUPERSEDED-BY;
     re-enter routing
   - **Wait & escalate** — exit, board unchanged
4. User chooses → corresponding path

## Out of scope (per spec §15)

- Type-2 (audit/RFC) and Type-3 (Local) item orchestration — handled ad-hoc
- Vollautomatic loop chaining without user confirmation — per Decision #7
- Auto-pickup in fork-session via marker files — explicitly manual copy-paste
- Cross-session FS state synchronization — board is single source of truth (Decision #9)
- PR review iteration helper (Pivot b) — left manual (Decision #8 b)
- Parallel item slot management — user self-discipline (Decision #8 d)
- LLM-generated branch names, PR titles, commit messages — all deterministic
- Schema migration of `items.json` to add `Goal` field — opt-in per item

## Common mistakes

| Mistake | Reality |
|---|---|
| Inventing a branch name in the handoff prompt | Violates `feedback_branch_naming`; resolve deterministically per the table |
| Suggesting "let's open an RFC first" for a strategic item | Violates `feedback_pr_first_for_strategic`; recommend PR-first |
| Surfacing a bug-labelled item without the (a)/(b)/(c) prompt | Violates `feedback_no_auto_bugfix` |
| Skipping `fetch.py` before mutating board card | Stale items.json overwrites maintainer edits |
| Writing the handoff prompt as freeform text | Use `templates/handoff-prompt.md.tpl`; freeform drift loses fields |
| Continuing on `status: blocked` without reading `## Pivot Reason` | Skips evidence; blind re-plan repeats the failure |
| Auto-running picker after bookkeeping without asking | Violates Decision #7 (halbautomatisch) |

## Red flags — STOP

- About to write a branch name not derivable from board-id / issue-number
- About to invoke `superpowers:writing-plans` without a spec on disk
- About to mutate `Status` without running `fetch.py` first
- About to skip the routing-assessment because "the path is obvious"
SKILL_EOF
```

- [ ] **Step 2: Verify file structure**

```bash
head -3 .claude/skills/emhass-cross-repo-flow/SKILL.md
grep -n "STATUS: PENDING" .claude/skills/emhass-cross-repo-flow/SKILL.md
grep -cE "^## " .claude/skills/emhass-cross-repo-flow/SKILL.md
```

Expected: frontmatter line; `STATUS: PENDING` found; section count ≥ 12.

- [ ] **Step 3: Cross-check that all four memory files are referenced by name**

```bash
for m in feedback_no_auto_bugfix feedback_pr_first_for_strategic feedback_branch_naming project_strategic_goals; do
  grep -q "$m" .claude/skills/emhass-cross-repo-flow/SKILL.md \
    && echo "$m: REFERENCED" \
    || echo "$m: MISSING"
done
```

Expected: all four print `REFERENCED`. If any prints `MISSING`, edit the SKILL.md to add the reference in the relevant section.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/emhass-cross-repo-flow/SKILL.md
git commit -m "feat(skill): add emhass-cross-repo-flow orchestration skill"
```

---

## Task 16: Extend `emhass-board-merge-bookkeeping` for closed-not-merged

**Goal:** Per spec §12.c — minimal extension. Description grows; one new section added; merge path unchanged.

**Files:**
- Modify: `.claude/skills/emhass-board-merge-bookkeeping/SKILL.md`

- [ ] **Step 1: Update frontmatter description**

Find the line in the file's frontmatter:

```yaml
description: Use when an upstream emhass PR is merged or closed-not-merged and the davidusb-geek/projects/2 board needs post-merge card moves. Triggers on phrases like "PR #N merged", "bookkeeping for PR", "board update for the merge", "ISSUE-N closed", or any merge-commit reference paired with the project board.
```

Replace with:

```yaml
description: Use when an upstream emhass PR is merged OR closed-without-merge and the davidusb-geek/projects/2 board needs post-PR card moves. Triggers on phrases like "PR #N merged", "PR #N closed", "PR #N wurde geschlossen, nicht gemerged", "won't-do for PR #N", "bookkeeping for PR", "board update for the merge", "ISSUE-N closed", or any PR-close reference paired with the project board.
```

Use the `Edit` tool with `old_string` matching the entire current description line and `new_string` set to the replacement above.

- [ ] **Step 2: Append the closed-not-merged section**

Append right before the existing `## Common mistakes` section:

````markdown
## Closed-without-merge mode

Trigger detection: `gh pr view <N> --repo davidusb-geek/emhass --json state,mergedAt`.

| `state` | `mergedAt` | Mode |
|---|---|---|
| `MERGED` | non-null | Standard merge bookkeeping (sections above) |
| `CLOSED` | `null` | Won't-do mode (this section) |

Won't-do mode: same Status target as merge bookkeeping (`Done / Wont Do` is a single
combined option in the project schema), but the script template marks PR-sibling
addition with a "closed-without-merge" intent and the commit message phrasing differs.

### Won't-do mode actions

1. **Read maintainer rationale** — `gh pr view <N> --repo davidusb-geek/emhass --comments`.
   Last 1-3 owner comments captured for documentation.
2. **Same case detection** — Case A (draft umbrella) or Case B (issue-only) per the
   sections above. Logic identical to merge path.
3. **Same Status target** — both Board-Card and PR-link card → `Status: Done / Wont Do`.
4. **PR-link card body** — when adding the PR-sibling card via `add_content_to_project`,
   the script template (Case B) populates the same fields, but the commit message reads
   `chore(board): PR #N closed without merge` (not `merged upstream`).

### Won't-do script template variant

```python
# Same imports + setup as merge template above
from lib import add_content_to_project, find_item, load_items, save_items, set_field

# Won't-do mode: same Status, different intent recorded in commit message.
PR_FIELDS = {"Status": "Done / Wont Do", "Category": "A: Code-Lifecycle",
             "Phase": "...", "Priority": "...", "Effort": "...", "Scope": "Upstream"}
WONT_DO_REASON = "<one-line summary of maintainer rationale>"  # for commit body

# ... rest identical to merge template ...
```

Commit message:

```
chore(board): PR #N closed without merge — <reason>
```

NOT `chore(board): PR #N merged upstream`.

### When to use

Invoke this mode when the user reports "PR #N wurde geschlossen, nicht gemerged" or when
`emhass-cross-repo-flow` Phase 8 detects `state=CLOSED, mergedAt=null` and the user picks
"Won't Do" from the spec §12.c options. Wait & escalate or Re-do paths do NOT trigger
this skill.
````

- [ ] **Step 3: Verify edits**

```bash
head -5 .claude/skills/emhass-board-merge-bookkeeping/SKILL.md
grep -n "Closed-without-merge" .claude/skills/emhass-board-merge-bookkeeping/SKILL.md
grep -n "merged or closed" .claude/skills/emhass-board-merge-bookkeeping/SKILL.md
```

Expected: frontmatter description matches the updated text; new section header found; description line found.

- [ ] **Step 4: Confirm merge-path content unchanged**

```bash
git diff .claude/skills/emhass-board-merge-bookkeeping/SKILL.md | head -100
```

Expected: only the description line is modified within the existing content; the new
section is purely additive (appears as `+` lines only); no `-` lines for sections like
`## Pre-flight`, `## Case A`, `## Case B`, `## One-shot script template`, `## Post-flight`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/emhass-board-merge-bookkeeping/SKILL.md
git commit -m "feat(skill): extend bookkeeping for closed-not-merged mode"
```

---

## Task 17: `emhass-next-item-picker` self-test execution

**Goal:** Run the script three times against live `items.json` per the SKILL.md self-test, verify idempotency + JSON validity + no bug-label leakage, then flip `STATUS: PENDING` → `STATUS: DONE`.

**Files:**
- Modify: `.claude/skills/emhass-next-item-picker/SKILL.md` (flip marker only)

- [ ] **Step 1: Execute the self-test commands**

```bash
python board/next.py --limit 3 > /tmp/picker-md-1.txt
python board/next.py --limit 3 > /tmp/picker-md-2.txt
python board/next.py --limit 3 --format json > /tmp/picker-json.txt
```

- [ ] **Step 2: Verify idempotency (Markdown)**

```bash
diff /tmp/picker-md-1.txt /tmp/picker-md-2.txt
```

Expected: empty output (files identical). If the test runs span midnight, the date header may differ — re-run within the same day or strip the first line before diffing.

- [ ] **Step 3: Verify JSON validity**

```bash
python -c "import json,sys; d=json.load(open('/tmp/picker-json.txt')); print('keys:', list(d.keys()))"
```

Expected: `keys: ['date', 'quickwins', 'strategics']`.

- [ ] **Step 4: Verify no bug-label leakage**

```bash
python -c "
import json
data = json.load(open('board/items.json'))
buggy = [it['id'] for it in data['items'] if 'bug' in (it.get('labels') or [])]
print('bug-labelled in items.json:', buggy)
"
```

Expected: `bug-labelled in items.json: []` (no labels field is currently populated). If
non-empty in future runs, also verify those IDs do not appear in the picker output:

```bash
python board/next.py --limit 50 | grep -E "<id-from-bug-list>" || echo "OK: not in default output"
```

- [ ] **Step 5: Flip STATUS marker**

Edit `.claude/skills/emhass-next-item-picker/SKILL.md`. Replace:

```markdown
**STATUS: PENDING.**
```

with:

```markdown
**STATUS: DONE — baseline executed YYYY-MM-DD against live `board/items.json`.**

Outcome: picker produced ranked Quick-Win + Strategic lists. Two consecutive runs
yielded identical output (idempotent). JSON output parsed cleanly. No bug-label
leakage (live items.json has no `labels` field populated; filter is dormant by
design until fetch.py is extended).
```

(Replace `YYYY-MM-DD` with today's actual date.)

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/emhass-next-item-picker/SKILL.md
git commit -m "chore(skill): mark emhass-next-item-picker self-test DONE"
```

---

## Task 18: `emhass-cross-repo-flow` self-test execution against AC-2a

**Goal:** Run the orchestration skill against AC-2a end-to-end up to handoff-prompt assembly + board status update. Stop **before** the fork session opens. No upstream code edits, no `git push` to fork, no upstream PR.

This is the live-run candidate from spec §13.3, executed in self-test bounds (§13.2 abort-before-PR pattern). Per the user's "out of scope" constraint, the AC-2a upstream code change is NOT executed.

**Files:**
- Create: `docs/superpowers/specs/2026-05-08-ac-2a-design.md` (via `templates/spec.md.tpl`)
- Create: `docs/superpowers/plans/2026-05-08-ac-2a.md` (via `superpowers:writing-plans`)
- Create: `board/2026-05-08-ac-2a-start.py` (status-mutation script)
- Modify: `board/items.json` (status moves from `Todo` → `In Progress` for AC-2a)
- Modify: `.claude/skills/emhass-cross-repo-flow/SKILL.md` (flip STATUS marker)

(Today's date when executing this task may differ from `2026-05-08`. Use the actual
execution date; the path examples here use 2026-05-08 because the skill was authored on
2026-05-07 and the self-test happens "at first use after authoring".)

- [ ] **Step 1: Pre-flight** (mirror SKILL.md Phase 0)

```bash
gh auth status                      # OptimalNothing90 active
git status                          # clean
git rev-parse --show-toplevel       # = emhass-contributions root
cd board && python fetch.py --dry-run   # 0 drift expected
cd ..
```

If drift > 0, run real `fetch.py`, commit `chore(board): refresh items.json before AC-2a self-test`, then proceed.

- [ ] **Step 2: Routing-assessment** (Phase 1)

Read AC-2a context:

```bash
python -c "
from board.lib import find_item, load_items
data = load_items()
it = find_item(data, 'AC-2a')
print(it)
" 2>/dev/null || python -c "
import json
data = json.load(open('board/items.json'))
print(next(it for it in data['items'] if it.get('id') == 'AC-2a'))
"
```

Confirm: Phase 1, P1, Effort S, Scope Upstream, Goal-fit `LLM-ready`.

Read the linked issue (#826):

```bash
gh issue view 826 --repo davidusb-geek/emhass --json title,body,labels,comments,author
```

Note: no `bug` label, no maintainer comment with solution direction.

Read the audit:

```bash
test -f audits/2026-04-28-param-definitions.md && head -20 audits/2026-04-28-param-definitions.md
```

Apply signal table → `plan-light` recommended (audit exists, no bug label, no maintainer engagement, LLM-ready strategic). Confirm with the user before continuing.

- [ ] **Step 3: Spec generation** (Phase 2 — plan-light path)

Render `.claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl` with these placeholder values:

| Placeholder | Value |
|---|---|
| `board_id` | `AC-2a` |
| `title` | `Add structured 'unit' field to param_definitions.json` |
| `date` | execution date in YYYY-MM-DD |
| `issue_link_or_none` | `https://github.com/davidusb-geek/emhass/issues/826` |
| `audit_path_or_none` | `audits/2026-04-28-param-definitions.md` |
| `branch_name` | `feat/ac-2a-unit-field` |
| `effort` | `S` |
| `phase` | `Phase 1` |
| `priority` | `P1` |
| `goal_fit` | `LLM-ready` |
| `problem_paragraph` | from issue body + audit findings (2-4 sentences) |
| `goal_sentence` | one sentence — adopt audit recommendation 1:1 |
| `decision_rows` | `| 1 | Adopt audit §X recommendation verbatim | audits/2026-04-28-param-definitions.md |` |
| `files_touched_list` | from audit findings |
| `concrete_edits_table` | from audit findings (≤10 rows) |
| `test_strategy_paragraph` | one paragraph |
| `acceptance_bullets` | 3-5 bullets |
| `out_of_scope_or_none` | optional |
| `memory_refs_or_none` | `project_strategic_goals.md` |

Write the rendered spec:

```bash
# pseudo: this happens through the skill flow, but for self-test bounds the rendered
# file is written directly with whatever date is current
cp .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl docs/superpowers/specs/$(date +%Y-%m-%d)-ac-2a-design.md
# … then sed-replace placeholders or hand-fill via $EDITOR
```

For the self-test, hand-filling the spec is acceptable (the skill in production would
delegate body content for `brainstorm` path; for `plan-light` it fills from item / audit
inputs). The objective here is to verify the **mechanism**, not the spec depth.

- [ ] **Step 4: Plan generation** (Phase 3)

Invoke `superpowers:writing-plans` skill with the spec path. The plan body covers the
upstream code work for AC-2a — but **the plan is written and saved only**. It is NOT
executed.

Plan path: `docs/superpowers/plans/$(date +%Y-%m-%d)-ac-2a.md`.

- [ ] **Step 5: Append handoff-prompt** (Phase 4)

Render `templates/handoff-prompt.md.tpl` with placeholders. Append to the plan as a
`## Handoff-Prompt` section.

```bash
PLAN=docs/superpowers/plans/$(date +%Y-%m-%d)-ac-2a.md
SPEC_PATH="docs/superpowers/specs/$(date +%Y-%m-%d)-ac-2a-design.md"
PLAN_PATH="$PLAN"

# Apply placeholder substitution (sed). If the template has special chars, use perl or
# manual edits.
sed -e "s|{{board_id}}|AC-2a|g" \
    -e "s|{{issue_link_or_none}}|https://github.com/davidusb-geek/emhass/issues/826|g" \
    -e "s|{{goal_fit}}|LLM-ready|g" \
    -e "s|{{spec_relative_path}}|$SPEC_PATH|g" \
    -e "s|{{plan_relative_path}}|$PLAN_PATH|g" \
    -e "s|{{branch_name}}|feat/ac-2a-unit-field|g" \
    -e "s|{{pr_title}}|feat(schema): add unit field to param_definitions.json (#826)|g" \
    -e "s|{{pr_body_skeleton}}|See spec at ../emhass-contributions/$SPEC_PATH sections 1+2+9; closes #826.|g" \
    .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl >> "$PLAN"
```

Verify the section was appended:

```bash
grep -n "^## Handoff-Prompt" "$PLAN"
grep -c '{{' "$PLAN"
```

Expected: section header found; placeholder count == 0 (all resolved).

- [ ] **Step 6: Board status update** (Phase 5)

Write a one-shot script:

```bash
cat > board/$(date +%Y-%m-%d)-ac-2a-start.py <<'EOF'
"""Self-test: AC-2a Status: Todo → In Progress."""
from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
assert item["Status"] == "Todo", f"unexpected Status: {item['Status']}"
set_field(PROJECT_ID, item["item_id"],
          field_ids["Status"], option_ids["Status"]["In Progress"])
item["Status"] = "In Progress"
save_items(data)
print(f"AC-2a → In Progress")
EOF
```

Run + verify:

```bash
cd board && python $(date +%Y-%m-%d)-ac-2a-start.py && python fetch.py --dry-run
cd ..
```

Expected: script prints success; dry-run shows 0 drift.

- [ ] **Step 7: STOP — abort before fork session opens**

**Do NOT** open a Claude Code session in `claude-code/emhass/`. **Do NOT** push to fork.
**Do NOT** open an upstream PR. **Do NOT** edit any files in `claude-code/emhass/`.

The self-test ends here. Verify all artefacts:

```bash
ls -la docs/superpowers/specs/$(date +%Y-%m-%d)-ac-2a-design.md
ls -la docs/superpowers/plans/$(date +%Y-%m-%d)-ac-2a.md
grep -A 5 '"id": "AC-2a"' board/items.json | grep '"Status":'
```

Expected: spec exists, plan exists with Handoff-Prompt section, items.json shows AC-2a `Status: In Progress`.

- [ ] **Step 8: Revert board card to Todo + cleanup**

Self-test artefacts must not pollute live state. Roll back:

```bash
cat > board/$(date +%Y-%m-%d)-ac-2a-revert.py <<'EOF'
"""Self-test rollback: AC-2a Status: In Progress → Todo."""
from lib import find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
BOARD_ID = "AC-2a"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]
item = find_item(data, BOARD_ID)
assert item["Status"] == "In Progress"
set_field(PROJECT_ID, item["item_id"],
          field_ids["Status"], option_ids["Status"]["Todo"])
item["Status"] = "Todo"
save_items(data)
EOF
cd board && python $(date +%Y-%m-%d)-ac-2a-revert.py && python fetch.py --dry-run
cd ..
```

Mark spec + plan files with self-test notice (do not delete; keep as audit trail):

```bash
DATE=$(date +%Y-%m-%d)
sed -i '1i> _Self-test artefact (cross-repo-flow). Do not treat as live work._\n' docs/superpowers/specs/$DATE-ac-2a-design.md
sed -i '1i> _Self-test artefact (cross-repo-flow). Do not treat as live work._\n' docs/superpowers/plans/$DATE-ac-2a.md
```

(`sed -i ''` on macOS; `sed -i` on GNU/Linux. Adjust if needed.)

- [ ] **Step 9: Flip STATUS marker**

Edit `.claude/skills/emhass-cross-repo-flow/SKILL.md`. Replace:

```markdown
**STATUS: PENDING.**
```

with (template — fill the date and outcome):

```markdown
**STATUS: DONE — baseline executed YYYY-MM-DD against AC-2a (board id `AC-2a`).**

Outcome: routing-assessment correctly recommended `plan-light` (audit + no bug + no
maintainer engagement). Spec + plan written at expected paths; handoff-prompt section
appended with all placeholders resolved including `branch_name=feat/ac-2a-unit-field`
(deterministic per `feedback_branch_naming`). Board card moved Todo → In Progress and
back to Todo for cleanup. Self-test stopped before fork session as designed; no
upstream PR opened. Spec + plan retained as `_self-test artefact_` — kept as audit
trail.

After STATUS: DONE, this section is audit trail only.
```

(Replace `YYYY-MM-DD` with the actual execution date.)

- [ ] **Step 10: Commit everything from this task**

```bash
git add docs/superpowers/specs/$(date +%Y-%m-%d)-ac-2a-design.md \
        docs/superpowers/plans/$(date +%Y-%m-%d)-ac-2a.md \
        board/$(date +%Y-%m-%d)-ac-2a-start.py \
        board/$(date +%Y-%m-%d)-ac-2a-revert.py \
        board/items.json \
        .claude/skills/emhass-cross-repo-flow/SKILL.md
git commit -m "chore(skill): mark emhass-cross-repo-flow self-test DONE (AC-2a)"
```

---

## Task 19: Final acceptance verification

**Goal:** Walk every spec §14 acceptance criterion, prove each, and produce one summary commit.

**Files:** none (verification only).

- [ ] **Step 1: Verify each acceptance bullet**

Run each command; record pass/fail. All must pass.

```bash
# AC1: board/next.py exists; CLI matches §8; all 14 unit tests pass
test -f board/next.py && echo "AC1.1 OK" || echo "AC1.1 FAIL"
python board/next.py --help | grep -E "\\-\\-mode|\\-\\-include-bugs|\\-\\-scope|\\-\\-limit|\\-\\-format" \
  && echo "AC1.2 OK" || echo "AC1.2 FAIL"
python -m pytest tests/test_board_next.py -v --tb=short \
  && echo "AC1.3 OK (all tests pass)" || echo "AC1.3 FAIL"

# AC2: fixture + tests exist; pytest clean
test -f tests/fixtures/items_sample.json && echo "AC2.1 OK" || echo "AC2.1 FAIL"
test -f tests/test_board_next.py && echo "AC2.2 OK" || echo "AC2.2 FAIL"

# AC3: pre-commit hook
grep -q "pytest-board-next" .pre-commit-config.yaml && echo "AC3 OK" || echo "AC3 FAIL"

# AC4: picker SKILL.md
test -f .claude/skills/emhass-next-item-picker/SKILL.md && echo "AC4 OK" || echo "AC4 FAIL"

# AC5: cross-repo-flow SKILL.md
test -f .claude/skills/emhass-cross-repo-flow/SKILL.md && echo "AC5 OK" || echo "AC5 FAIL"

# AC6: templates exist
test -f .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl && echo "AC6.1 OK" || echo "AC6.1 FAIL"
test -f .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl && echo "AC6.2 OK" || echo "AC6.2 FAIL"

# AC7: bookkeeping skill extension
grep -q "merged or closed" .claude/skills/emhass-board-merge-bookkeeping/SKILL.md \
  && echo "AC7.1 OK" || echo "AC7.1 FAIL"
grep -q "Closed-without-merge" .claude/skills/emhass-board-merge-bookkeeping/SKILL.md \
  && echo "AC7.2 OK" || echo "AC7.2 FAIL"

# AC8: cross-repo-flow self-test STATUS = DONE
grep -q "STATUS: DONE" .claude/skills/emhass-cross-repo-flow/SKILL.md \
  && echo "AC8 OK" || echo "AC8 FAIL"

# AC9: picker self-test STATUS = DONE
grep -q "STATUS: DONE" .claude/skills/emhass-next-item-picker/SKILL.md \
  && echo "AC9 OK" || echo "AC9 FAIL"

# AC10: live-run AC-2a self-test artefacts present
ls docs/superpowers/specs/*-ac-2a-design.md > /dev/null 2>&1 && echo "AC10.1 OK" || echo "AC10.1 FAIL"
ls docs/superpowers/plans/*-ac-2a.md > /dev/null 2>&1 && echo "AC10.2 OK" || echo "AC10.2 FAIL"
```

Every line must end `OK`.

- [ ] **Step 2: Run pre-commit on all touched files**

```bash
pre-commit run --files \
  board/next.py \
  tests/__init__.py \
  tests/test_board_next.py \
  tests/fixtures/items_sample.json \
  .pre-commit-config.yaml \
  .claude/skills/emhass-next-item-picker/SKILL.md \
  .claude/skills/emhass-cross-repo-flow/SKILL.md \
  .claude/skills/emhass-cross-repo-flow/templates/spec.md.tpl \
  .claude/skills/emhass-cross-repo-flow/templates/handoff-prompt.md.tpl \
  .claude/skills/emhass-board-merge-bookkeeping/SKILL.md
```

Expected: every hook reports `Passed`.

- [ ] **Step 3: Verify branch-name discipline**

Before merging, confirm the implementation branch followed `feedback_branch_naming`:

```bash
git rev-parse --abbrev-ref HEAD
```

Expected: `chore/cross-repo-flow`. If not, the work happened on a different branch — flag for user before merging.

- [ ] **Step 4: Final summary commit (optional)**

If any small drift was fixed during verification:

```bash
git add -p
git commit -m "chore(cross-repo-flow): final acceptance fixes"
```

If nothing changed, skip this step.

- [ ] **Step 5: Decide merge strategy**

The `chore/cross-repo-flow` branch is now ready. Options to surface to user:

- `git checkout main && git merge --ff-only chore/cross-repo-flow` (fast-forward)
- Open a self-PR for review history (`gh pr create --base main --head chore/cross-repo-flow ...`)
- Squash-merge if commit history is too granular

Per `feedback_branch_naming`'s spirit, this is internal infra, not an upstream PR — the user picks how to land it. Default suggestion: fast-forward merge.

---

## Self-Review Checklist

Run this checklist after completing all tasks but before declaring the plan executed.

**1. Spec coverage:**
- [ ] §6 file layout — every path in the table exists or is justified absent (✅ all created in Tasks 2-16)
- [ ] §8 CLI flags + filter rules + ranking — Task 4-10 (✅)
- [ ] §9 spec template — Task 12 (✅)
- [ ] §10 handoff-prompt template — Task 13 (✅)
- [ ] §11 routing-mini-assessment — Task 15 SKILL.md Phase 1 (✅)
- [ ] §12.a pivot (plan-wrong) — Task 15 SKILL.md Pivot pathway (a) (✅)
- [ ] §12.c pivot (closed-not-merged) — Task 15 SKILL.md Pivot pathway (c) + Task 16 bookkeeping extension (✅)
- [ ] §13.1 14 unit tests — Tasks 4, 5, 6, 7, 8, 9 (✅)
- [ ] §13.2 self-tests for both new skills — Tasks 17, 18 (✅)
- [ ] §13.3 live-run AC-2a — Task 18 (bounded scope: stops before fork session) (✅)
- [ ] §14 acceptance criteria — Task 19 (✅)
- [ ] §15 out-of-scope honoured — no upstream code edits, no `Goal` schema migration, no marker-file IPC (✅)

**2. Placeholder scan:** None of the tasks contain "TBD", "TODO", "implement later", "fill in details", "add appropriate error handling", "similar to Task N", or other deferral phrasings. (Verified by writing concrete code/templates inline.)

**3. Type / name consistency:**
- [ ] `filter_candidates(items, *, scope, include_bugs)` — Task 4, 5
- [ ] `rank_quickwin(items)`, `rank_strategic(items)` — Task 6
- [ ] `goal_fit(item)` — Task 7
- [ ] `why_quick(item)`, `why_strategic(item)` — Task 8
- [ ] `render_markdown(quickwins, strategics, *, today)` — Task 8
- [ ] `render_json(quickwins, strategics, *, today)` — Task 9
- [ ] `main(argv)` — Task 10

All test calls match these signatures (verified by re-reading Tasks 4-10).

If any inconsistency is discovered during execution, fix in place; no need to re-review.
