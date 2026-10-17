from datetime import datetime, timedelta, timezone

import pytest

from flexd.config import TemplateDefinition
from flexd.models import Demand
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
    # expiry stays deadline+ttl: now+ttl is earlier and must not win (#1 HIGH 2).
    # The old assertion (expires_at > first_expiry) compared real-now+1h against
    # this 2026-07-05 fixture and passed vacuously.
    assert d.expires_at == first_expiry
    assert d.expires_at > d.deadline
    assert len(reg.list_active(now=t0)) == 1


def test_retrigger_long_before_deadline_keeps_run_alive(tmp_path):
    # LesIT1's repro: dishwasher-by-06:30 double-pressed at 20:27 and 20:28 Berlin
    reg, mgr = mk(tmp_path)
    t0 = datetime(2026, 7, 5, 18, 27, tzinfo=timezone.utc)  # 20:27 Berlin, evening rule
    mgr.start("dishwasher", source="loxone", now=t0)
    deadline = reg.get("dishwasher").deadline
    mgr.start("dishwasher", source="loxone", now=t0 + timedelta(minutes=1))
    d = reg.get("dishwasher")
    assert d.deadline == deadline
    assert d.expires_at == deadline + timedelta(hours=1)
    # still active at the deadline: the sweep must not have a reason to drop it before then
    assert reg.list_active(now=deadline - timedelta(minutes=1))


def test_trigger_in_post_deadline_grace_starts_new_run(tmp_path):
    reg, mgr = mk(tmp_path)
    t0 = datetime(
        2026, 7, 5, 6, 0, tzinfo=timezone.utc
    )  # 08:00 Berlin -> deadline 15:00 Berlin
    mgr.start("dishwasher", source="loxone", now=t0)
    old_deadline = reg.get("dishwasher").deadline
    # 10 min after the deadline, inside the 1 h grace (expires_at > now): a real new run
    t1 = old_deadline + timedelta(minutes=10)  # 15:10 Berlin, no bracket -> default 8 h
    mgr.start("dishwasher", source="loxone", now=t1)
    d = reg.get("dishwasher")
    assert d.deadline == t1 + timedelta(hours=8)
    assert d.deadline > old_deadline


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


# -- Codex review 2026-10-16 finding 5: re-trigger needs deadline > now AND expires_at > now --
def test_trigger_after_expiry_but_before_sweep_starts_new_run(tmp_path):
    reg, mgr = mk(tmp_path)
    t0 = datetime(
        2026, 7, 5, 6, 0, tzinfo=timezone.utc
    )  # deadline 15:00 Berlin, expiry 16:00 Berlin
    mgr.start("dishwasher", source="loxone", now=t0)
    first = reg.get("dishwasher")
    t1 = first.expires_at + timedelta(minutes=5)  # expired, not yet swept
    mgr.start("dishwasher", source="loxone", now=t1)
    d = reg.get("dishwasher")
    assert d.deadline > t1
    assert d.expires_at > t1


def test_trigger_on_expired_but_pending_run_starts_new_run(tmp_path):
    # expires_at <= now < deadline: the old refresh-by-deadline branch would have refreshed
    # an expired entry; now it must be a new run (review of Task 2)
    reg, mgr = mk(tmp_path)
    t0 = datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc)
    for t1 in (
        t0 + timedelta(minutes=30),
        t0 + timedelta(minutes=31),
    ):  # exact boundary and after
        reg.upsert(
            Demand(
                id="dishwasher",
                source="loxone",
                energy_target_wh=1400,
                nominal_power_w=2000,
                deadline=t0 + timedelta(hours=9),
                expires_at=t0 + timedelta(minutes=30),
                ttl_s=1800,
            )
        )
        mgr.start("dishwasher", source="loxone", now=t1)
        d = reg.get("dishwasher")
        assert d.expires_at > t1
        assert d.deadline == datetime(
            2026, 7, 5, 13, 0, tzinfo=timezone.utc
        )  # 15:00 Berlin from the morning rule


def test_template_modulating_flag_reaches_demand(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    tpl = TemplateDefinition(
        id="heater",
        nominal_power_w=3000,
        energy_wh=1500,
        modulating=True,
        default_finish_in_h=4,
    )
    mgr = TemplateManager([tpl], tz="UTC", registry=reg, default_ttl_s=3600)
    mgr.start(
        "heater", source="loxone", now=datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc)
    )
    assert reg.get("heater").modulating is True


# -- #1 Medium 3: not_before on the far side of midnight was anchored to the trigger day --
NIGHT_TPL = TemplateDefinition(
    id="dryer",
    nominal_power_w=2000,
    energy_wh=1400,
    deadline_rules=[
        {
            "if_started_between": "20:00-06:00",
            "not_before": "01:00",
            "finish_by": "06:30",
        },
    ],
)


def test_not_before_past_midnight_anchors_to_next_day(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    mgr = TemplateManager(
        [NIGHT_TPL], tz="Europe/Berlin", registry=reg, default_ttl_s=3600
    )
    # 22:00 Berlin on 07-05 == 20:00 UTC; not_before 01:00 Berlin is 23:00 UTC the same day
    mgr.start(
        "dryer", source="loxone", now=datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    )
    d = reg.get("dryer")
    assert d.deadline == datetime(
        2026, 7, 6, 4, 30, tzinfo=timezone.utc
    )  # 06:30 Berlin
    assert d.window_start == datetime(
        2026, 7, 5, 23, 0, tzinfo=timezone.utc
    )  # 01:00 Berlin


def test_not_before_same_day_when_still_ahead(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    mgr = TemplateManager(
        [NIGHT_TPL], tz="Europe/Berlin", registry=reg, default_ttl_s=3600
    )
    # 00:30 Berlin on 07-06 == 22:30 UTC on 07-05; not_before 01:00 Berlin is 30 min ahead
    mgr.start(
        "dryer", source="loxone", now=datetime(2026, 7, 5, 22, 30, tzinfo=timezone.utc)
    )
    d = reg.get("dryer")
    assert d.deadline == datetime(2026, 7, 6, 4, 30, tzinfo=timezone.utc)
    assert d.window_start == datetime(2026, 7, 5, 23, 0, tzinfo=timezone.utc)
