"""Tests for prototypes/flags.py."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from prototypes import flags


def _reset_cache() -> None:
    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})


def test_missing_file_returns_false(tmp_path: Path):
    """A non-existent flags file means all features are off."""
    nonexistent = tmp_path / "no-such-file.yaml"
    _reset_cache()

    assert flags.is_enabled("api_last_run", path=nonexistent) is False
    assert flags.is_enabled("api_healthz", path=nonexistent) is False
    assert flags.is_enabled("anything_else", path=nonexistent) is False


def test_empty_file_returns_false(tmp_path: Path):
    """An empty YAML file should result in all features off."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    _reset_cache()

    assert flags.is_enabled("api_last_run", path=empty) is False


def test_feature_enabled_returns_true(tmp_path: Path):
    """A flag explicitly set enabled: true should return True."""
    cfg = tmp_path / "enabled.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
"""
    )
    _reset_cache()

    assert flags.is_enabled("api_last_run", path=cfg) is True
    assert flags.is_enabled("api_healthz", path=cfg) is False  # other feature still off


def test_invalid_yaml_returns_false_with_log(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Malformed YAML should not crash; should log warning + return all-off."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - not really yaml [\n")
    _reset_cache()

    with caplog.at_level("WARNING", logger="emhass.contrib.flags"):
        result = flags.is_enabled("api_last_run", path=bad)

    assert result is False
    assert any(
        "unreadable" in rec.message or "not a dict" in rec.message
        for rec in caplog.records
    )


def test_get_setting_returns_feature_specific_value(tmp_path: Path):
    """get_setting should return per-feature settings, with default fallback."""
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
    cache_seconds: 60
"""
    )
    _reset_cache()

    assert flags.get_setting("api_last_run", "cache_seconds", path=cfg) == 60
    assert flags.get_setting("api_last_run", "missing_key", default="x", path=cfg) == "x"
    assert flags.get_setting("nonexistent_feature", "anything", default=None, path=cfg) is None


def test_cache_invalidates_on_mtime_change(tmp_path: Path):
    """Editing the file should invalidate cache before TTL expires."""
    cfg = tmp_path / "live.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: false
"""
    )
    _reset_cache()

    # First read: disabled
    assert flags.is_enabled("api_last_run", path=cfg) is False

    # Edit the file with a newer mtime (force, since some FSs round mtime)
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
"""
    )
    new_mtime = cfg.stat().st_mtime + 10
    os.utime(cfg, (new_mtime, new_mtime))

    # Second read: should reflect the change despite no TTL expiry
    assert flags.is_enabled("api_last_run", path=cfg) is True
