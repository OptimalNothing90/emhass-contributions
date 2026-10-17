"""Persisted pending-clear queue (#1 Medium 11, remainder)."""

import json

from flexd.pending_clear import PendingClear


def test_add_persists_and_reloads(tmp_path):
    p = tmp_path / "pending_clear.json"
    q = PendingClear(p)
    q.add(["a", "b"])
    assert q.ids() == ["a", "b"]
    assert PendingClear(p).ids() == ["a", "b"]  # survives a restart


def test_remove_persists(tmp_path):
    p = tmp_path / "pending_clear.json"
    q = PendingClear(p)
    q.add(["a", "b", "c"])
    q.remove(["a", "c"])
    assert q.ids() == ["b"]
    assert PendingClear(p).ids() == ["b"]


def test_remove_only_the_given_ids_keeps_newer_arrivals(tmp_path):
    q = PendingClear(tmp_path / "pending_clear.json")
    q.add(["a"])
    snapshot = q.ids()
    q.add(["b"])  # arrived while `snapshot` was being delivered
    q.remove(snapshot)
    assert q.ids() == ["b"]


def test_add_is_idempotent(tmp_path):
    q = PendingClear(tmp_path / "pending_clear.json")
    q.add(["a"])
    q.add(["a"])
    assert q.ids() == ["a"]


def test_unreadable_file_starts_empty(tmp_path):
    p = tmp_path / "pending_clear.json"
    p.write_text("{not json", encoding="utf-8")
    assert PendingClear(p).ids() == []


def test_bounded_keeps_the_newest(tmp_path):
    q = PendingClear(tmp_path / "pending_clear.json", max_ids=3)
    q.add([f"g{i}" for i in range(5)])
    assert q.ids() == ["g2", "g3", "g4"]


def test_memory_only_without_path():
    q = PendingClear()
    q.add(["a"])
    assert q.ids() == ["a"]


def test_write_goes_through_tmp_and_replace(tmp_path, monkeypatch):
    import os

    import flexd.pending_clear as mod

    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(mod.os, "replace", spy)
    p = tmp_path / "pending_clear.json"
    PendingClear(p).add(["a"])
    assert replaced and replaced[0][0].endswith(".tmp")
    assert json.loads(p.read_text(encoding="utf-8")) == ["a"]
