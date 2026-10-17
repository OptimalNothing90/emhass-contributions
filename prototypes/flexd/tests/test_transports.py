"""Shared transport gate: live_demand_view (registry truth over the adopted plan)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flexd.plan_view import PlanView
from flexd.transports import live_demand_view
from tests.conftest import make_demand

FIX = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
PLAN = json.loads((FIX / "plan_ok.json").read_text(encoding="utf-8"))
MAPPING = {"dishwasher": {"slot": 0, "clamped": False, "nominal_power_w": 2000}}


def adopted_view(tmp_path, now=T0):
    view = PlanView(tmp_path / "adopted_plan.json", stale_after=timedelta(hours=2))
    view.adopt(PLAN, MAPPING, now=now)
    return view


# -- Codex review 2026-10-17 finding 1: the early-serve rule must never put a setpoint
#    outside [window_start, deadline) ----------------------------------------------------
def test_before_window_start_reads_off(registry, tmp_path):
    # the plan's first record (2000 W at 12:00) is served up to one step early, but the
    # demand may not start before 12:00
    view = adopted_view(tmp_path, now=T0 - timedelta(minutes=10))
    registry.upsert(
        make_demand(
            window_start=T0,
            deadline=T0 + timedelta(hours=4),
            expires_at=T0 + timedelta(hours=5),
        )
    )
    dv, status = live_demand_view(
        registry, view, "dishwasher", now=T0 - timedelta(minutes=10)
    )
    assert status == "outside-window"
    assert dv.setpoint_w == 0 and dv.on is False


def test_from_window_start_the_plan_is_served(registry, tmp_path):
    view = adopted_view(tmp_path, now=T0 - timedelta(minutes=10))
    registry.upsert(
        make_demand(
            window_start=T0,
            deadline=T0 + timedelta(hours=4),
            expires_at=T0 + timedelta(hours=5),
        )
    )
    dv, status = live_demand_view(registry, view, "dishwasher", now=T0)
    assert status == "ok"
    assert dv.setpoint_w == 2000 and dv.on is True


def test_at_or_after_deadline_reads_off(registry, tmp_path):
    # deadline inside the served slot: the slot is 12:00-12:30, the deadline 12:10
    view = adopted_view(tmp_path)
    registry.upsert(
        make_demand(
            deadline=T0 + timedelta(minutes=10), expires_at=T0 + timedelta(hours=1)
        )
    )
    dv, status = live_demand_view(
        registry, view, "dishwasher", now=T0 + timedelta(minutes=5)
    )
    assert status == "ok" and dv.setpoint_w == 2000
    for now in (T0 + timedelta(minutes=10), T0 + timedelta(minutes=20)):
        dv, status = live_demand_view(registry, view, "dishwasher", now=now)
        assert status == "outside-window"
        assert dv.setpoint_w == 0 and dv.on is False


def test_window_gate_runs_after_expiry_and_pending(registry, tmp_path):
    view = adopted_view(tmp_path)
    registry.upsert(
        make_demand(
            id="pool",  # not in the adopted mapping
            window_start=T0 + timedelta(hours=1),
            deadline=T0 + timedelta(hours=4),
            expires_at=T0 + timedelta(hours=5),
        )
    )
    assert live_demand_view(registry, view, "pool", now=T0) == (None, "pending")
    registry.upsert(
        make_demand(
            window_start=T0 + timedelta(hours=1),
            deadline=T0 + timedelta(hours=4),
            expires_at=T0 + timedelta(hours=5),
        )
    )
    _, status = live_demand_view(
        registry, view, "dishwasher", now=T0 + timedelta(hours=5)
    )
    assert status == "expired"
