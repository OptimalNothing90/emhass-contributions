import json
from datetime import datetime, timedelta, timezone

import pytest

from flexd.registry import OwnershipError, Registry
from tests.conftest import make_demand


def test_upsert_and_get(registry):
    d = make_demand()
    registry.upsert(d)
    assert registry.get("dishwasher").source == "loxone"
    assert len(registry.list_active()) == 1


def test_upsert_cross_source_rejected(registry):
    registry.upsert(make_demand())
    with pytest.raises(OwnershipError):
        registry.upsert(make_demand(source="homeassistant"))


def test_delete_cross_source_rejected(registry):
    registry.upsert(make_demand())
    with pytest.raises(OwnershipError):
        registry.delete("dishwasher", source="homeassistant")
    registry.delete("dishwasher", source="loxone")
    assert registry.get("dishwasher") is None


def test_refresh_bumps_expires_by_ttl(registry):
    d = make_demand()
    registry.upsert(d)
    old = registry.get("dishwasher").expires_at
    registry.refresh("dishwasher", source="loxone")
    new = registry.get("dishwasher").expires_at
    assert new > old  # now + ttl_s > created_at + ttl_s


def test_sweep_drops_expired(registry):
    now = datetime.now(timezone.utc)
    registry.upsert(make_demand(id="old", expires_at=now + timedelta(seconds=1)))
    registry.upsert(make_demand(id="fresh"))
    swept = registry.sweep(now=now + timedelta(seconds=2))
    assert [d.id for d in swept] == ["old"]
    assert [d.id for d in registry.list_active()] == ["fresh"]


def test_persistence_roundtrip(tmp_path):
    r1 = Registry(tmp_path / "demands.json")
    r1.upsert(make_demand())
    r2 = Registry(tmp_path / "demands.json")
    assert r2.get("dishwasher") is not None


def test_corrupt_file_falls_back_to_bak(tmp_path):
    path = tmp_path / "demands.json"
    r1 = Registry(path)
    r1.upsert(make_demand())
    r1.upsert(
        make_demand(id="second")
    )  # second write -> .bak now holds valid prior state
    path.write_text("{corrupt", encoding="utf-8")
    r2 = Registry(path)
    assert r2.get("dishwasher") is not None  # loaded from .bak


def test_corrupt_file_and_bak_starts_empty(tmp_path):
    path = tmp_path / "demands.json"
    path.write_text("{corrupt", encoding="utf-8")
    (tmp_path / "demands.json.bak").write_text("also corrupt", encoding="utf-8")
    r = Registry(path)
    assert r.list_active() == []


def test_returned_objects_are_copies(registry):
    d = make_demand()
    registry.upsert(d)
    got = registry.get("dishwasher")
    got.energy_target_wh = 99999
    assert registry.get("dishwasher").energy_target_wh == 1200
    listed = registry.list_active()[0]
    listed.energy_target_wh = 88888
    assert registry.get("dishwasher").energy_target_wh == 1200
    d.energy_target_wh = 77777  # caller's original object also decoupled
    assert registry.get("dishwasher").energy_target_wh == 1200
    ret = registry.upsert(make_demand(id="r2"))
    ret.energy_target_wh = 66666
    assert registry.get("r2").energy_target_wh == 1200


def test_delete_queues_the_id_for_retained_topic_clear(registry):
    registry.upsert(make_demand())
    registry.delete("dishwasher", source="loxone")
    assert registry.pending_clear.ids() == ["dishwasher"]
    registry.pending_clear.remove(["dishwasher"])
    assert registry.pending_clear.ids() == []


def test_concurrent_writers_no_corruption(tmp_path):
    import threading

    reg = Registry(tmp_path / "demands.json", max_demands=100)  # 90 writes below
    errors = []

    def writer(prefix):
        try:
            for n in range(30):
                reg.upsert(make_demand(id=f"{prefix}-{n}"))
                reg.sweep()
                reg.list_active()
        except Exception as exc:  # noqa: BLE001 — any exception is the failure signal
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(p,)) for p in ("aaa", "bbb", "ccc")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    reloaded = Registry(tmp_path / "demands.json")
    assert len(reloaded.list_active()) == 90  # every write survived


# -- #1 HIGH 2: refresh recomputed expires_at from the wall clock and could shorten --
def test_refresh_never_moves_expiry_earlier(registry):
    now = datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    deadline = now + timedelta(hours=10)
    registry.upsert(
        make_demand(
            deadline=deadline, expires_at=deadline + timedelta(hours=1), ttl_s=3600
        )
    )
    before = registry.get("dishwasher").expires_at
    after = registry.refresh(
        "dishwasher", source="loxone", now=now + timedelta(minutes=1)
    ).expires_at
    assert after == before  # deadline+1h is later than now+1h: keep it
    assert after > deadline


def test_refresh_extends_when_ttl_window_is_later(registry):
    now = datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    registry.upsert(
        make_demand(
            deadline=now + timedelta(hours=8),
            expires_at=now + timedelta(minutes=30),
            ttl_s=3600,
        )
    )
    after = registry.refresh("dishwasher", source="loxone", now=now).expires_at
    assert after == now + timedelta(hours=1)


def test_refresh_stamps_updated_at_with_pinned_now(registry):
    now = datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    registry.upsert(make_demand())
    d = registry.refresh("dishwasher", source="loxone", now=now)
    assert d.updated_at == now


# -- Codex review 2026-10-16 finding 2: one bad entry must not empty the registry --
def test_load_skips_one_bad_entry_keeps_the_rest(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    reg.upsert(make_demand(id="good-a"))
    reg.upsert(make_demand(id="good-b"))
    raw = json.loads((tmp_path / "demands.json").read_text(encoding="utf-8"))
    raw["demands"].append(
        {"id": "broken", "source": "loxone"}
    )  # missing required fields
    (tmp_path / "demands.json").write_text(json.dumps(raw), encoding="utf-8")
    reloaded = Registry(tmp_path / "demands.json")
    assert sorted(d.id for d in reloaded.list_active()) == ["good-a", "good-b"]


def test_load_falls_back_to_bak_only_when_file_is_not_json(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    reg.upsert(make_demand(id="first"))
    reg.upsert(make_demand(id="second"))  # rotates the one-demand state into .bak
    (tmp_path / "demands.json").write_text("{not json", encoding="utf-8")
    reloaded = Registry(tmp_path / "demands.json")
    assert [d.id for d in reloaded.list_active()] == ["first"]


def test_refreshed_far_expiry_demand_reloads(tmp_path):
    # refresh lifts expires_at but keeps created_at and ttl_s: the persisted ttl no longer
    # equals expires_at - created_at and must still reload (review finding 2)
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    reg = Registry(tmp_path / "demands.json")
    reg.upsert(
        make_demand(
            created_at=now,  # pinned: ttl derives from created_at, not the wall clock
            deadline=now + timedelta(days=300),
            expires_at=now + timedelta(days=301),
        )
    )
    reg.refresh("dishwasher", source="loxone", now=now + timedelta(seconds=2))
    reloaded = Registry(tmp_path / "demands.json")
    assert reloaded.get("dishwasher") is not None
    assert reloaded.get("dishwasher").ttl_s == pytest.approx(301 * 24 * 3600, rel=1e-3)


def test_explicit_ttl_with_matching_timestamps_still_rejected():
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(Exception):
        make_demand(
            created_at=now,
            deadline=now + timedelta(days=399),
            expires_at=now + timedelta(days=400),
            ttl_s=400 * 24 * 3600,
        )


def test_load_malformed_container_falls_back_to_bak(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    reg.upsert(make_demand(id="first"))
    reg.upsert(make_demand(id="second"))  # one-demand state now in .bak
    (tmp_path / "demands.json").write_text('{"demands": null}', encoding="utf-8")
    assert [d.id for d in Registry(tmp_path / "demands.json").list_active()] == [
        "first"
    ]
    (tmp_path / "demands.json").write_text('{"demands": {"a": 1}}', encoding="utf-8")
    assert [d.id for d in Registry(tmp_path / "demands.json").list_active()] == [
        "first"
    ]


# -- Codex review 2026-10-16 finding 5: refresh must not revive an expired demand --
def test_refresh_of_expired_demand_is_rejected(registry):
    now = datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    registry.upsert(
        make_demand(
            deadline=now - timedelta(hours=1),
            expires_at=now - timedelta(minutes=5),
            ttl_s=3600,
        )
    )
    with pytest.raises(KeyError):
        registry.refresh("dishwasher", source="loxone", now=now)
    assert registry.list_active(now=now) == []  # still expired, nothing revived


# -- #1 Medium 12: every refresh rewrote the whole registry file --
def test_refresh_bursts_coalesce_into_one_save(tmp_path, monkeypatch):
    import time

    reg = Registry(tmp_path / "demands.json", save_debounce_s=0.3)
    saves = []
    real_save = reg._save
    monkeypatch.setattr(reg, "_save", lambda: (saves.append(1), real_save()))
    reg.upsert(make_demand(ttl_s=3600))  # explicit write, flushes immediately
    assert len(saves) == 1
    for _ in range(10):
        reg.refresh("dishwasher", source="loxone")
    assert len(saves) == 1  # inside the debounce window: nothing written yet
    time.sleep(0.6)
    assert len(saves) == 2  # one deferred write for the whole burst
    on_disk = Registry(tmp_path / "demands.json").get("dishwasher")
    assert on_disk.expires_at == reg.get("dishwasher").expires_at


def test_flush_writes_a_pending_refresh_now(tmp_path):
    reg = Registry(tmp_path / "demands.json", save_debounce_s=60)
    reg.upsert(make_demand(ttl_s=3600))
    before = Registry(tmp_path / "demands.json").get("dishwasher").expires_at
    reg.refresh("dishwasher", source="loxone")
    assert Registry(tmp_path / "demands.json").get("dishwasher").expires_at == before
    reg.flush()
    on_disk = Registry(tmp_path / "demands.json").get("dishwasher").expires_at
    assert on_disk == reg.get("dishwasher").expires_at


def test_upsert_and_delete_flush_a_pending_refresh(tmp_path):
    reg = Registry(tmp_path / "demands.json", save_debounce_s=60)
    reg.upsert(make_demand(ttl_s=3600))
    reg.refresh("dishwasher", source="loxone")
    refreshed = reg.get("dishwasher").expires_at
    reg.upsert(make_demand(id="other"))
    assert Registry(tmp_path / "demands.json").get("dishwasher").expires_at == refreshed


def test_register_beyond_max_demands_rejected(tmp_path):
    from flexd.registry import RegistryFull

    reg = Registry(tmp_path / "demands.json", max_demands=2)
    reg.upsert(make_demand(id="aaa"))
    reg.upsert(make_demand(id="bbb"))
    with pytest.raises(RegistryFull):
        reg.upsert(make_demand(id="ccc"))
    reg.upsert(make_demand(id="aaa", energy_target_wh=900))  # re-declaring is fine
    assert reg.get("aaa").energy_target_wh == 900
    reg.delete("bbb", source="loxone")
    reg.upsert(make_demand(id="ccc"))  # room again
    assert len(reg.list_active()) == 2


def test_expired_demands_do_not_count_against_max(tmp_path):
    now = datetime.now(timezone.utc)
    reg = Registry(tmp_path / "demands.json", max_demands=1)
    reg.upsert(
        make_demand(
            id="old",
            deadline=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
    )
    reg.upsert(make_demand(id="new"))  # the expired one is not folded into a payload
    assert [d.id for d in reg.list_active()] == ["new"]


# -- #1 Lows: no write path fsynced before os.replace --
def test_save_fsyncs_before_replace(tmp_path, monkeypatch):
    import flexd.registry as mod

    events = []
    real_fsync, real_replace = mod.os.fsync, mod.os.replace
    monkeypatch.setattr(
        mod.os, "fsync", lambda fd: (events.append("fsync"), real_fsync(fd))
    )
    monkeypatch.setattr(
        mod.os, "replace", lambda a, b: (events.append("replace"), real_replace(a, b))
    )
    Registry(tmp_path / "demands.json").upsert(make_demand())
    assert events and events[0] == "fsync"
    assert events.index("fsync") < events.index("replace")
