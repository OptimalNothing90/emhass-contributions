import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    },
    "pool": {"slot": 1, "clamped": True, "truncated": False, "unschedulable": False},
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
