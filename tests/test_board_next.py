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
