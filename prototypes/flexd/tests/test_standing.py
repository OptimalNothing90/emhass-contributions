import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from flexd.config import StandingDefinition
from flexd.models import Demand
from flexd.plan_view import PlanView
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


def test_live_cycle_instants_accrue_against_real_plan(tmp_path):
    # end-to-end for #1 HIGH 1: the scheduler's since/until are wall-clock instants a
    # few seconds past the grid; with the real PlanView the ledger must still shrink
    # (on main this left energy_target_wh at the full 15000 Wh every cycle).
    reg, mgr = mk(tmp_path)
    view = PlanView(tmp_path / "adopted.json", stale_after=timedelta(hours=2))
    plan = {
        "status": "Optimal",
        "generated_at": "2026-07-05T12:00:05Z",
        "emhass_schema_version": 1,
        "plan": [
            {"timestamp": "2026-07-05T12:00:00Z", "P_deferrable0": 3000},
            {"timestamp": "2026-07-05T12:30:00Z", "P_deferrable0": 3000},
            {"timestamp": "2026-07-05T13:00:00Z", "P_deferrable0": 0},
        ],
    }
    mapping = {"waterheater": {"slot": 0, "clamped": False, "nominal_power_w": 3000}}
    view.adopt(plan, mapping, now=NOON_UTC)

    c1 = NOON_UTC + timedelta(seconds=7)  # 12:00:07
    c2 = NOON_UTC + timedelta(minutes=30, seconds=12)  # 12:30:12
    mgr.materialize(now=c1, elapsed_lookup=view.on_hours_elapsed)
    mgr.materialize(now=c2, elapsed_lookup=view.on_hours_elapsed)

    on_seconds = (c2 - NOON_UTC).total_seconds()  # heater on from 12:00:00 to 12:30:12
    expected_remaining_h = 5 - on_seconds / 3600
    assert reg.get("waterheater").energy_target_wh == pytest.approx(
        expected_remaining_h * 3000
    )


# -- Codex review 2026-10-16 finding 4: accrue the old plan up to the real switch --
def test_accrue_only_updates_ledger_without_materializing(tmp_path):
    reg, mgr = mk(tmp_path)
    mgr.accrue(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 1.5)
    assert reg.get("waterheater") is None  # accrue never touches the registry
    mgr.materialize(
        now=NOON_UTC + timedelta(minutes=1), elapsed_lookup=lambda i, s, u: 0.0
    )
    assert reg.get("waterheater").energy_target_wh == pytest.approx((5 - 1.5) * 3000)


async def test_energy_accounting_across_a_real_plan_switch(tmp_path):
    from flexd.scheduler import Scheduler

    reg, mgr = mk(tmp_path)
    view = PlanView(
        tmp_path / "adopted.json",
        stale_after=timedelta(hours=2),
        timestep=timedelta(minutes=30),
    )

    def plan(power, generated_at, first):
        return {
            "status": "ok",
            "generated_at": generated_at,
            "emhass_schema_version": "1.0",
            "plan": [
                {
                    "timestamp": (first + timedelta(minutes=30 * i)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "P_deferrable0": power,
                }
                for i in range(3)
            ],
        }

    plans = [
        plan(3000, "2026-07-05T12:00:05Z", NOON_UTC),
        plan(1500, "2026-07-05T12:30:05Z", NOON_UTC + timedelta(minutes=30)),
        plan(1500, "2026-07-05T13:00:05Z", NOON_UTC + timedelta(hours=1)),
    ]

    class TwoPlans:
        async def run_cycle(self, payload, last_generated_at=None):
            return plans.pop(0)

    ticks = iter(
        [
            NOON_UTC + timedelta(minutes=2),
            NOON_UTC + timedelta(minutes=31, seconds=30),
            NOON_UTC + timedelta(minutes=61),
        ]
    )
    s = Scheduler(
        registry=reg,
        driver=TwoPlans(),
        view=view,
        standing=mgr,
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        clock=lambda: next(ticks),
    )

    await s.run_once(now=NOON_UTC)  # adopt A at 12:02
    # A credited 12:02-12:30 and 12:30-12:31:30; adopt B at 12:31:30
    await s.run_once(now=NOON_UTC + timedelta(minutes=30))
    # B credited 12:31:30-13:00 at 1500/3000 before this solve
    await s.run_once(now=NOON_UTC + timedelta(hours=1))
    expected_elapsed_h = 28 / 60 + 1.5 / 60 + 28.5 / 60 * 0.5
    assert reg.get("waterheater").energy_target_wh == pytest.approx(
        (5 - expected_elapsed_h) * 3000, abs=1.0
    )


def test_standing_modulating_flag_reaches_demand(tmp_path):
    reg = Registry(tmp_path / "demands.json")
    defn = StandingDefinition(
        id="pump",
        nominal_power_w=750,
        daily_hours=4,
        window="06:00-22:00",
        modulating=True,
    )
    mgr = StandingManager(
        [defn], ledger_path=tmp_path / "ledger.json", tz="Europe/Berlin", registry=reg
    )
    mgr.materialize(now=NOON_UTC, elapsed_lookup=lambda i, s, u: 0.0)
    assert reg.get("pump").modulating is True
