import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from flexd.config import StandingDefinition
from flexd.models import Demand
from flexd.registry import Registry
from flexd.standing import StandingManager

BERLIN = ZoneInfo("Europe/Berlin")
# 2026-07-05 12:00 UTC == 14:00 Berlin, inside an 06:00-22:00 window
NOON_UTC = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
NIGHT_UTC = datetime(2026, 7, 5, 22, 0, tzinfo=timezone.utc)  # 00:00 Berlin next day

DEF = StandingDefinition(
    id="waterheater", nominal_power_w=3000, daily_hours=5, window="06:00-22:00"
)


def mk(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    mgr = StandingManager(
        [DEF], ledger_path=tmp_path / "ledger.json", tz="Europe/Berlin", registry=reg
    )
    return reg, mgr


def test_materializes_inside_window(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    d = reg.get("waterheater")
    assert d is not None
    assert d.source == "config"
    assert d.energy_target_wh == 5 * 3000
    # expires at today's window end: 22:00 Berlin == 20:00 UTC
    assert d.expires_at == datetime(2026, 7, 5, 20, 0, tzinfo=timezone.utc)
    assert d.deadline == d.expires_at


def test_not_materialized_outside_window(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NIGHT_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("waterheater") is None


def test_elapsed_reduces_remaining(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 2.0)
    assert reg.get("waterheater").energy_target_wh == 3 * 3000  # 5h target - 2h accrued


def test_accrual_accumulates_across_cycles(tmp_path):
    reg, mgr = mk(tmp_path)
    intervals = []

    def lookup(i, s, u):
        intervals.append((s, u))
        return 0.5

    mgr.materialize(now=NOON_UTC, elapsed_lookup=lookup)
    assert reg.get("waterheater").energy_target_wh == 4.5 * 3000
    later = NOON_UTC + timedelta(minutes=30)
    mgr.materialize(now=later, elapsed_lookup=lookup)
    assert reg.get("waterheater").energy_target_wh == 4.0 * 3000  # 0.5 + 0.5 accrued
    # first interval starts at window start (06:00 Berlin == 04:00 UTC), second at last accrual
    assert intervals[0] == (datetime(2026, 7, 5, 4, 0, tzinfo=timezone.utc), NOON_UTC)
    assert intervals[1] == (NOON_UTC, later)


def test_same_now_does_not_double_accrue(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 2.0)
    mgr.materialize(
        now=NOON_UTC, elapsed_lookup=lambda i, s, u: 99.0
    )  # empty interval: not called
    assert reg.get("waterheater").energy_target_wh == 3 * 3000


def test_correction_rebases_target(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 2.0)
    mgr.correct("waterheater", remaining_hours=1.0, now=NOON_UTC)
    # override = 1 + elapsed_h(2) = 3h day target; remaining = 3 - 2 = 1h
    mgr.materialize(
        now=NOON_UTC, elapsed_lookup=lambda i, s, u: 99.0
    )  # no new accrual (same now)
    assert reg.get("waterheater").energy_target_wh == 1 * 3000


def test_correct_to_zero_removes_demand(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("waterheater") is not None
    mgr.correct(
        "waterheater", remaining_hours=0.0, now=NOON_UTC
    )  # "nothing left today"
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("waterheater") is None  # override 0.0 must not be discarded as falsy


def test_satisfied_target_removes_registry_entry(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 2.0)
    assert reg.get("waterheater") is not None
    later = NOON_UTC + timedelta(hours=1)
    mgr.materialize(now=later, elapsed_lookup=lambda i, s, u: 3.0)  # total 5h == target
    assert reg.get("waterheater") is None  # stale instance must not keep soliciting


def test_done_today_skips_until_midnight(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    mgr.mark_done("waterheater", now=NOON_UTC)
    assert reg.get("waterheater") is None  # removed
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("waterheater") is None  # not re-upserted
    # next Berlin day 07:00 == 05:00 UTC on 07-06
    next_day = datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc)
    mgr.materialize(now=next_day, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("waterheater") is not None


def test_ledger_survives_restart(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.mark_done("waterheater", now=NOON_UTC)
    reg2 = Registry(tmp_path / "demands.json")
    mgr2 = StandingManager(
        [DEF], ledger_path=tmp_path / "ledger.json", tz="Europe/Berlin", registry=reg2
    )
    mgr2.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg2.get("waterheater") is None


def test_target_fully_consumed_not_materialized(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 5.0)
    assert reg.get("waterheater") is None


def test_squatted_id_degrades_one_demand_not_the_cycle(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    # a dynamic demand squats the standing id before materialize runs
    reg.upsert(
        Demand(
            id="waterheater",
            source="loxone",
            energy_target_wh=1000,
            nominal_power_w=2000,
            deadline=NOON_UTC + timedelta(hours=4),
            expires_at=NOON_UTC + timedelta(hours=4),
        )
    )
    other = StandingDefinition(
        id="bbb-heater", nominal_power_w=1000, daily_hours=2, window="06:00-22:00"
    )
    mgr = StandingManager(
        [DEF, other],
        ledger_path=tmp_path / "ledger.json",
        tz="Europe/Berlin",
        registry=reg,
    )
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)  # must not raise
    assert reg.get("bbb-heater") is not None  # sibling still materialized
    assert reg.get("waterheater").source == "loxone"  # squatter untouched


def test_naive_last_accrual_tolerated(tmp_path):
    # a hand-edited or legacy ledger may carry a naive last_accrual string
    (tmp_path / "ledger.json").write_text(
        json.dumps(
            {
                "waterheater:2026-07-05": {
                    "done": False,
                    "day_target_override_h": None,
                    "elapsed_h": 1.0,
                    "last_accrual": "2026-07-05T11:00:00",  # naive: treated as UTC
                }
            }
        ),
        encoding="utf-8",
    )
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)  # must not crash
    assert reg.get("waterheater") is not None


def test_past_day_ledger_keys_pruned(tmp_path):
    (tmp_path / "ledger.json").write_text(
        json.dumps(
            {
                "waterheater:2026-07-04": {
                    "done": True,
                    "day_target_override_h": None,
                    "elapsed_h": 5.0,
                    "last_accrual": None,
                }
            }
        ),
        encoding="utf-8",
    )
    reg, mgr = mk(tmp_path)
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    saved = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert "waterheater:2026-07-04" not in saved
    assert "waterheater:2026-07-05" in saved


def test_unknown_id_correct_raises(tmp_path):
    reg, mgr = mk(tmp_path)
    with pytest.raises(KeyError):
        mgr.correct("not-a-standing-id", remaining_hours=1.0, now=NOON_UTC)
    with pytest.raises(KeyError):
        mgr.mark_done("not-a-standing-id", now=NOON_UTC)
