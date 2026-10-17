"""Tests for the testable parts of skills/emhass-pr-readiness/scripts.

check_param_definitions.py enforces AGENTS.md don't-touch rule 4 (param_definitions.json
is additive only) between two versions of the file. pr_readiness.sh itself needs a git
checkout of EMHASS and is smoke-tested only (--help), its full run is manual.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "emhass-pr-readiness" / "scripts"
CHECK = SCRIPTS / "check_param_definitions.py"
SH = SCRIPTS / "pr_readiness.sh"

OLD = {
    "Local": {
        "costfun": {
            "input": "select",
            "select_options": ["profit", "cost"],
            "default_value": "profit",
        },
        "logging_level": {"input": "select", "select_options": ["INFO", "DEBUG"]},
    },
    "Battery": {
        "set_use_battery": {"input": "boolean", "default_value": False},
    },
}


def _run(old: dict, new: dict, tmp_path: Path):
    a = tmp_path / "old.json"
    b = tmp_path / "new.json"
    a.write_text(json.dumps(old), encoding="utf-8")
    b.write_text(json.dumps(new), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-I", str(CHECK), str(a), str(b)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_identical_files_pass(tmp_path):
    proc = _run(OLD, OLD, tmp_path)
    assert proc.returncode == 0
    assert "[OK]" in proc.stdout


def test_added_key_passes_and_is_listed(tmp_path):
    new = copy.deepcopy(OLD)
    new["Battery"]["number_of_batteries"] = {"input": "int", "default_value": 1}
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 0
    assert "number_of_batteries" in proc.stdout


def test_removed_key_fails(tmp_path):
    new = copy.deepcopy(OLD)
    del new["Local"]["logging_level"]
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 1
    assert "[FAIL]" in proc.stdout and "logging_level" in proc.stdout


def test_changed_input_kind_fails(tmp_path):
    new = copy.deepcopy(OLD)
    new["Battery"]["set_use_battery"]["input"] = "int"
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 1
    assert "set_use_battery" in proc.stdout and "boolean" in proc.stdout


def test_removed_select_option_fails(tmp_path):
    new = copy.deepcopy(OLD)
    new["Local"]["costfun"]["select_options"] = ["profit"]
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 1
    assert "cost" in proc.stdout


def test_added_select_option_passes(tmp_path):
    new = copy.deepcopy(OLD)
    new["Local"]["costfun"]["select_options"].append("self-consumption")
    assert _run(OLD, new, tmp_path).returncode == 0


def test_moved_key_between_sections_is_warn_not_fail(tmp_path):
    new = copy.deepcopy(OLD)
    new["Local"]["set_use_battery"] = new["Battery"].pop("set_use_battery")
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 0
    assert "[WARN]" in proc.stdout and "set_use_battery" in proc.stdout


def test_changed_default_is_warn(tmp_path):
    new = copy.deepcopy(OLD)
    new["Battery"]["set_use_battery"]["default_value"] = True
    proc = _run(OLD, new, tmp_path)
    assert proc.returncode == 0
    assert "[WARN]" in proc.stdout and "config_defaults.json" in proc.stdout


def test_unreadable_file_exits_two(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            str(CHECK),
            str(tmp_path / "a.json"),
            str(tmp_path / "b.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2


def _bash() -> str | None:
    """Prefer Git Bash on Windows (the System32 bash.exe is WSL and cannot see C:/ paths)."""
    git = shutil.which("git")
    if git and sys.platform == "win32":
        root = Path(git).resolve().parent.parent
        for candidate in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
            if candidate.exists():
                return str(candidate)
    return shutil.which("bash")


@pytest.mark.skipif(_bash() is None, reason="bash not available")
def test_shell_script_help_runs():
    proc = subprocess.run(
        [_bash(), SH.as_posix(), "--help"],  # Git Bash needs forward slashes
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, proc.stderr
    assert "--base" in proc.stdout and "--no-tests" in proc.stdout
