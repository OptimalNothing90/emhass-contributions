from datetime import datetime, timedelta, timezone

import pytest

from flexd.config import TemplateDefinition
from flexd.registry import Registry
from flexd.templates import TemplateManager

TPL = TemplateDefinition(
    id="dishwasher",
    nominal_power_w=2000,
    energy_wh=1400,
    interruptible=False,
    default_finish_in_h=8,
    deadline_rules=[
        {"if_started_between": "06:00-12:00", "finish_by": "15:00"},
        {
            "if_started_between": "20:00-06:00",
            "not_before": "21:30",
            "finish_by": "06:30",
        },
    ],
)


def mk(tmp_path, tz="Europe/Berlin"):
    reg = Registry(tmp_path / "demands.json")
    return reg, TemplateManager([TPL], tz=tz, registry=reg, default_ttl_s=3600)


def test_morning_start_same_day_deadline(tmp_path):
    reg, mgr = mk(tmp_path)
    # 08:00 Berlin == 06:00 UTC (July, CEST)
    mgr.start(
        "dishwasher",
        source="loxone",
        now=datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc),
    )
    d = reg.get("dishwasher")
    assert d.source == "loxone"
    assert d.interruptible is False
    assert d.energy_target_wh == 1400
    # finish_by 15:00 Berlin == 13:00 UTC same day
    assert d.deadline == datetime(2026, 7, 5, 13, 0, tzinfo=timezone.utc)
    assert d.window_start is None  # no not_before in the morning rule


def test_evening_start_next_day_deadline_and_not_before(tmp_path):
    reg, mgr = mk(tmp_path)
    # 22:00 Berlin == 20:00 UTC — inside the 20:00-06:00 wrap bracket
    mgr.start(
        "dishwasher",
        source="loxone",
        now=datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc),
    )
    d = reg.get("dishwasher")
    # finish_by 06:30 <= bracket start time-of-day -> next Berlin day == 04:30 UTC on 07-06
    assert d.deadline == datetime(2026, 7, 6, 4, 30, tzinfo=timezone.utc)
    # not_before 21:30 Berlin is in the past at 22:00 -> no window_start
    assert d.window_start is None


def test_not_before_in_future_sets_window_start(tmp_path):
    reg, mgr = mk(tmp_path)
    # 21:00 Berlin == 19:00 UTC; not_before 21:30 Berlin == 19:30 UTC
    mgr.start(
        "dishwasher",
        source="loxone",
        now=datetime(2026, 7, 5, 19, 0, tzinfo=timezone.utc),
    )
    assert reg.get("dishwasher").window_start == datetime(
        2026, 7, 5, 19, 30, tzinfo=timezone.utc
    )


def test_gap_falls_back_to_default(tmp_path):
    reg, mgr = mk(tmp_path)
    # 14:00 Berlin == 12:00 UTC — no bracket covers 12:00-20:00
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    mgr.start("dishwasher", source="loxone", now=now)
    d = reg.get("dishwasher")
    assert (d.deadline - now).total_seconds() == 8 * 3600


def test_retrigger_is_pure_refresh_deadline_stable(tmp_path):
    reg, mgr = mk(tmp_path)
    t0 = datetime(2026, 7, 5, 9, 55, tzinfo=timezone.utc)  # 11:55 Berlin, morning rule
    mgr.start("dishwasher", source="loxone", now=t0)
    first_deadline = reg.get("dishwasher").deadline
    first_expiry = reg.get("dishwasher").expires_at
    # flapping trigger 10 min later — now 12:05 Berlin, a DIFFERENT (gap/default) bracket
    mgr.start("dishwasher", source="loxone", now=t0 + timedelta(minutes=10))
    d = reg.get("dishwasher")
    assert d.deadline == first_deadline  # deadline computed once, never moved
    assert d.expires_at > first_expiry  # only expiry bumped (refresh)
    assert len(reg.list_active(now=t0)) == 1


def test_unknown_template_raises(tmp_path):
    _, mgr = mk(tmp_path)
    with pytest.raises(KeyError):
        mgr.start(
            "dryer",
            source="loxone",
            now=datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc),
        )


def test_overlapping_brackets_fatal():
    with pytest.raises(ValueError, match="overlap"):
        TemplateDefinition(
            id="bad",
            nominal_power_w=1,
            energy_wh=1,
            deadline_rules=[
                {"if_started_between": "06:00-12:00", "finish_by": "15:00"},
                {"if_started_between": "11:00-14:00", "finish_by": "16:00"},
            ],
        )
