"""The README promises stdlib Python 3.10+: no 3.11-only names in the helper scripts
(Codex review 2026-10-17 finding 10)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parent.parent).glob("emhass-*/scripts/*.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_no_datetime_utc_import(script: Path):
    tree = ast.parse(script.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            names = {alias.name for alias in node.names}
            assert "UTC" not in names, f"{script}: datetime.UTC needs Python 3.11+"
