"""Unit tests for board/next.py picker logic.

Tests load tests/fixtures/items_sample.json and exercise individual
filter / ranking / rendering functions. No GitHub API, no live items.json.
"""

from __future__ import annotations

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
