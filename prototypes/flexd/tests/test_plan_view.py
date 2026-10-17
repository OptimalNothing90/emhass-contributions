import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from flexd.plan_view import PlanView

FIX = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
PLAN = json.loads((FIX / "plan_ok.json").read_text(encoding="utf-8"))
MAPPING = {
    "dishwasher": {
        "slot": 0,
        "clamped": False,
        "truncated": False,
        "unschedulable": False,
        "nominal_power_w": 2000,
    },
    "pool": {
        "slot": 1,
        "clamped": True,
        "truncated": False,
        "unschedulable": False,
        "nominal_power_w": 3000,
    },
}


def make_view(tmp_path):
    return PlanView(tmp_path / "adopted_plan.json", stale_after=timedelta(hours=2))


def test_no_run_before_any_adoption(tmp_path):
    v = make_view(tmp_path)
    assert v.state(now=T0) == "no-run"
    assert v.demand_view("dishwasher", now=T0) is None


def test_setpoint_current_timestep(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    dv = v.demand_view("dishwasher", now=T0 + timedelta(minutes=5))
    assert dv.setpoint_w == 2000
    assert dv.on is True
    assert dv.clamped is False
    dv2 = v.demand_view("pool", now=T0 + timedelta(minutes=5))
    assert dv2.setpoint_w == 0
    assert dv2.on is False
    assert dv2.clamped is True


def test_setpoint_second_timestep(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    dv = v.demand_view("pool", now=T0 + timedelta(minutes=35))
    assert dv.setpoint_w == 3000
    assert dv.on is True


def test_stale_after_threshold(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    assert v.state(now=T0 + timedelta(hours=1)) == "ok"
    assert v.state(now=T0 + timedelta(hours=3)) == "stale"


def test_past_plan_end_is_setpoint_zero(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    dv = v.demand_view("dishwasher", now=T0 + timedelta(hours=5))
    assert dv.setpoint_w == 0
    assert dv.on is False


def test_persistence_roundtrip(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    v2 = make_view(tmp_path)
    assert v2.state(now=T0) == "ok"
    assert v2.demand_view("dishwasher", now=T0).setpoint_w == 2000
    assert v2.generated_at == PLAN["generated_at"]  # restart contract: survives reload


def test_on_hours_elapsed_today(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    # by 13:00 UTC, dishwasher was on for the 12:00-12:30 slot = 0.5 h
    assert (
        v.on_hours_elapsed("dishwasher", since=T0, until=T0 + timedelta(hours=1)) == 0.5
    )


def test_reload_into_stale_after_downtime(tmp_path):
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    v2 = make_view(tmp_path)  # restart after 3h downtime
    assert v2.state(now=T0 + timedelta(hours=3)) == "stale"


def test_demand_view_exposes_flags(tmp_path):
    v = make_view(tmp_path)
    mapping = {
        "dishwasher": {
            "slot": 0,
            "clamped": False,
            "truncated": True,
            "unschedulable": False,
        },
    }
    v.adopt(PLAN, mapping, now=T0)
    dv = v.demand_view("dishwasher", now=T0)
    assert dv.truncated is True
    assert dv.unschedulable is False


def test_corrupt_view_file_starts_no_run(tmp_path):
    path = tmp_path / "adopted_plan.json"
    path.write_text("{broken", encoding="utf-8")
    v = PlanView(path, stale_after=timedelta(hours=2))
    assert v.state(now=T0) == "no-run"


# -- #1 HIGH 1: live cycle bounds never sit on the grid; partial slots must count --
def test_on_hours_elapsed_off_grid_live_instants(tmp_path):
    # 12:00:07 -> 12:30:12 must still credit the 12:00-12:30 slot; the old
    # fully-inside rule returned 0.0 on every live cycle
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    got = v.on_hours_elapsed(
        "dishwasher",
        since=T0 + timedelta(seconds=7),
        until=T0 + timedelta(minutes=30, seconds=12),
    )
    assert got == pytest.approx(
        (30 * 60 - 7) / 3600
    )  # 12:00:07 .. 12:30:00 on, then off


def test_on_hours_elapsed_partition_invariant(tmp_path):
    # adjacent off-grid intervals covering [12:00, 13:00) sum to the aligned answer
    v = make_view(tmp_path)
    v.adopt(PLAN, MAPPING, now=T0)
    cuts = [
        T0,
        T0 + timedelta(seconds=7),
        T0 + timedelta(minutes=30, seconds=12),
        T0 + timedelta(hours=1),
    ]
    total = sum(
        v.on_hours_elapsed("dishwasher", since=a, until=b)
        for a, b in zip(cuts, cuts[1:])
    )
    assert total == pytest.approx(0.5)


def test_on_hours_elapsed_scales_by_power_ratio(tmp_path):
    # Medium 6: a 1000 W slot on a 2000 W nominal load is 0.25 nominal-hours, not 0.5
    v = make_view(tmp_path)
    plan = json.loads(json.dumps(PLAN))
    plan["plan"][0]["P_deferrable0"] = 1000
    v.adopt(plan, MAPPING, now=T0)
    assert v.on_hours_elapsed(
        "dishwasher", since=T0, until=T0 + timedelta(hours=1)
    ) == pytest.approx(0.25)


def test_on_hours_elapsed_legacy_mapping_without_nominal(tmp_path):
    # adopted_plan.json written before this fix has no nominal_power_w: full-slot credit
    v = make_view(tmp_path)
    legacy = {"dishwasher": {"slot": 0, "clamped": False}}
    v.adopt(PLAN, legacy, now=T0)
    assert (
        v.on_hours_elapsed("dishwasher", since=T0, until=T0 + timedelta(hours=1)) == 0.5
    )


# -- Codex review 2026-10-16 finding 4: single-record plans use the configured step --
def test_single_record_uses_configured_timestep(tmp_path):
    v = PlanView(
        tmp_path / "adopted.json",
        stale_after=timedelta(hours=2),
        timestep=timedelta(minutes=15),
    )
    plan = json.loads(json.dumps(PLAN))
    plan["plan"] = plan["plan"][:1]  # one record, 2000 W
    v.adopt(plan, MAPPING, now=T0)
    assert v.on_hours_elapsed(
        "dishwasher", since=T0, until=T0 + timedelta(hours=1)
    ) == pytest.approx(0.25)
    assert v.demand_view("dishwasher", now=T0 + timedelta(minutes=20)) is not None
    assert (
        v.demand_view("dishwasher", now=T0 + timedelta(minutes=20)).setpoint_w == 0
    )  # past the single 15-min record


# -- #1 Lows: the adopted-plan write fsyncs before the swap (it has no .bak) --
def test_adopt_fsyncs_before_replace(tmp_path, monkeypatch):
    import flexd.plan_view as mod

    events = []
    real_fsync, real_replace = mod.os.fsync, mod.os.replace
    monkeypatch.setattr(
        mod.os, "fsync", lambda fd: (events.append("fsync"), real_fsync(fd))
    )
    monkeypatch.setattr(
        mod.os, "replace", lambda a, b: (events.append("replace"), real_replace(a, b))
    )
    make_view(tmp_path).adopt(PLAN, MAPPING, now=T0)
    assert events == ["fsync", "replace"]
