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
