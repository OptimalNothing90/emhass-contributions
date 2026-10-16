from datetime import datetime, timedelta, timezone

import pytest

from flexd.aggregator import build_runtimeparams, grid_anchor
from tests.conftest import make_demand

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
CFG = dict(timestep_min=30, horizon_steps=48)


def test_single_demand_payload():
    d = make_demand(
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["number_of_deferrable_loads"] == 1
    assert payload["nominal_power_of_deferrable_loads"] == [2000]
    assert payload["operating_hours_of_each_deferrable_load"] == [
        1.0
    ]  # 1200 Wh / 2000 W = 0.6 h, rounded UP to 2 x 30 min (non-modulating default)
    assert payload["start_timesteps_of_each_deferrable_load"] == [0]
    assert payload["end_timesteps_of_each_deferrable_load"] == [8]  # 4h / 30min
    assert payload["def_current_power"] == [0]
    assert payload["prediction_horizon"] == 48
    assert mapping == {
        "dishwasher": {
            "slot": 0,
            "clamped": False,
            "truncated": False,
            "unschedulable": False,
            "nominal_power_w": 2000,
            "modulating": False,
            "timesteps": 2,
            "anchor": NOW.isoformat(),
        }
    }


def test_slots_sorted_by_id():
    d1 = make_demand(
        id="zebra",
        expires_at=NOW + timedelta(hours=5),
        deadline=NOW + timedelta(hours=4),
    )
    d2 = make_demand(
        id="alpha",
        expires_at=NOW + timedelta(hours=5),
        deadline=NOW + timedelta(hours=4),
    )
    _, mapping = build_runtimeparams([d1, d2], now=NOW, extra={}, **CFG)
    assert mapping["alpha"]["slot"] == 0
    assert mapping["zebra"]["slot"] == 1


def test_deadline_beyond_horizon_clamped():
    d = make_demand(
        deadline=NOW + timedelta(hours=48), expires_at=NOW + timedelta(hours=49)
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["end_timesteps_of_each_deferrable_load"] == [48]
    assert mapping["dishwasher"]["clamped"] is True


def test_window_start_in_future():
    d = make_demand(
        window_start=NOW + timedelta(hours=2),
        deadline=NOW + timedelta(hours=6),
        expires_at=NOW + timedelta(hours=7),
    )
    payload, _ = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["start_timesteps_of_each_deferrable_load"] == [4]


def test_extra_params_merged_but_never_override():
    d = make_demand(
        deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
    )
    payload, _ = build_runtimeparams(
        [d],
        now=NOW,
        extra={
            "soc_init": 0.5,
            "def_total_hours": [99],
            "operating_hours_of_each_deferrable_load": [77],
        },
        **CFG,
    )
    assert payload["soc_init"] == 0.5
    assert payload["operating_hours_of_each_deferrable_load"] == [1.0]  # flexd wins
    assert "def_total_hours" not in payload  # legacy alias blocked entirely


def test_current_power_passthrough():
    d = make_demand(
        current_power_w=1500,
        deadline=NOW + timedelta(hours=4),
        expires_at=NOW + timedelta(hours=5),
    )
    payload, _ = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["def_current_power"] == [1500]


def test_expired_deadline_unschedulable():
    d = make_demand(
        deadline=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(hours=1)
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["operating_hours_of_each_deferrable_load"] == [0.0]
    assert mapping["dishwasher"]["unschedulable"] is True


def test_end_step_floors_not_ceils():
    d = make_demand(
        deadline=NOW + timedelta(minutes=105), expires_at=NOW + timedelta(hours=3)
    )
    payload, _ = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["end_timesteps_of_each_deferrable_load"] == [
        3
    ]  # floor(3.5), never past deadline


def test_unreachable_energy_truncated_to_window():
    d = make_demand(
        energy_target_wh=10000,
        nominal_power_w=2000,
        deadline=NOW + timedelta(hours=1),
        expires_at=NOW + timedelta(hours=2),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["operating_hours_of_each_deferrable_load"] == [
        1.0
    ]  # capacity, not 5.0
    assert mapping["dishwasher"]["truncated"] is True


def test_micro_demand_never_rounds_to_zero():
    d = make_demand(
        energy_target_wh=10,
        nominal_power_w=3000,
        deadline=NOW + timedelta(hours=4),
        expires_at=NOW + timedelta(hours=5),
    )
    payload, _ = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    # non-modulating: at least one whole slot, never zero (silent vanish)
    assert payload["operating_timesteps_of_each_deferrable_load"] == [1]
    assert payload["operating_hours_of_each_deferrable_load"] == [0.5]


def test_unschedulable_demand_pin_zeroed():
    d = make_demand(
        current_power_w=1800,
        deadline=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["def_current_power"] == [0]
    assert mapping["dishwasher"]["unschedulable"] is True


def test_truncated_hours_never_exceed_capacity_odd_timestep():
    d = make_demand(
        energy_target_wh=10000,
        nominal_power_w=2000,
        deadline=NOW + timedelta(minutes=10),
        expires_at=NOW + timedelta(hours=1),
    )
    payload, _ = build_runtimeparams(
        [d], now=NOW, extra={}, timestep_min=10, horizon_steps=48
    )
    # one full ten-minute slot: capacity is 1 step, never more than the window
    assert payload["operating_timesteps_of_each_deferrable_load"] == [1]
    assert payload["operating_hours_of_each_deferrable_load"] == [
        pytest.approx(10 / 60)
    ]


def test_mapping_carries_nominal_power():
    # #1 HIGH 1 / Medium 6: read-back accrual scales P_deferrable by nominal power
    d = make_demand(nominal_power_w=2000)
    _, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert mapping["dishwasher"]["nominal_power_w"] == 2000


# -- Codex review 2026-10-16 finding 1 / #1 Medium 5: whole slots for semi-continuous loads --
def test_non_modulating_load_emits_whole_timesteps_and_semi_cont():
    # 1200 Wh at 2000 W = 0.6 h; on a 30-min semi-continuous grid that is unreachable.
    # Round up to 2 slots and let upstream use the timestep form.
    d = make_demand(
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["treat_deferrable_load_as_semi_cont"] == [True]
    assert payload["operating_timesteps_of_each_deferrable_load"] == [2]
    assert payload["operating_hours_of_each_deferrable_load"] == [1.0]  # 2 x 30 min
    assert mapping["dishwasher"]["modulating"] is False
    assert mapping["dishwasher"]["timesteps"] == 2


def test_modulating_load_keeps_fractional_hours_and_continuous():
    d = make_demand(
        modulating=True,
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["treat_deferrable_load_as_semi_cont"] == [False]
    assert payload["operating_timesteps_of_each_deferrable_load"] == [
        0
    ]  # 0 = use hours
    assert payload["operating_hours_of_each_deferrable_load"] == [0.6]
    assert mapping["dishwasher"]["modulating"] is True
    assert mapping["dishwasher"]["timesteps"] == 0


def test_timesteps_capped_to_window():
    # 3 h wanted inside a 2 h window: 4 steps capacity, truncated, never more than the window
    d = make_demand(
        energy_target_wh=6000,
        deadline=NOW + timedelta(hours=2),
        window_start=None,
        expires_at=NOW + timedelta(hours=3),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["operating_timesteps_of_each_deferrable_load"] == [4]
    assert mapping["dishwasher"]["truncated"] is True


def test_unschedulable_load_emits_zero_timesteps_and_hours():
    d = make_demand(
        deadline=NOW - timedelta(hours=1),
        window_start=None,
        expires_at=NOW + timedelta(hours=1),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["operating_timesteps_of_each_deferrable_load"] == [0]
    assert payload["operating_hours_of_each_deferrable_load"] == [0.0]
    assert mapping["dishwasher"]["unschedulable"] is True


def test_extra_cannot_override_semi_cont_or_timesteps():
    d = make_demand(
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    extra = {
        "treat_deferrable_load_as_semi_cont": [False],
        "treat_def_as_semi_cont": [False],
        "operating_timesteps_of_each_deferrable_load": [9],
    }
    payload, _ = build_runtimeparams([d], now=NOW, extra=extra, **CFG)
    assert payload["treat_deferrable_load_as_semi_cont"] == [True]
    assert payload["operating_timesteps_of_each_deferrable_load"] == [2]
    assert "treat_def_as_semi_cont" not in payload


def test_mixed_loads_emit_consistent_per_load_arrays():
    a = make_demand(
        id="a-dishwasher",
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    b = make_demand(
        id="b-heater",
        modulating=True,
        nominal_power_w=3000,
        energy_target_wh=1800,
        deadline=NOW + timedelta(hours=4),
        window_start=None,
        expires_at=NOW + timedelta(hours=5),
    )
    payload, mapping = build_runtimeparams([a, b], now=NOW, extra={}, **CFG)
    assert payload["treat_deferrable_load_as_semi_cont"] == [True, False]
    assert payload["operating_timesteps_of_each_deferrable_load"] == [2, 0]
    assert payload["operating_hours_of_each_deferrable_load"] == [1.0, 0.6]
    assert all(
        len(payload[k]) == 2
        for k in (
            "nominal_power_of_deferrable_loads",
            "start_timesteps_of_each_deferrable_load",
            "end_timesteps_of_each_deferrable_load",
            "def_current_power",
        )
    )


def test_subnormal_power_does_not_crash_aggregation():
    # plan review finding 4: wanted_h overflows to inf; the quotient must be guarded
    d = make_demand(
        nominal_power_w=1e-308,
        energy_target_wh=1000,
        deadline=NOW + timedelta(hours=2),
        window_start=None,
        expires_at=NOW + timedelta(hours=3),
    )
    payload, mapping = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["operating_timesteps_of_each_deferrable_load"] == [4]
    assert mapping["dishwasher"]["truncated"] is True


# -- plan review finding 3: flexd anchors its grid like EMHASS method_ts_round --
@pytest.mark.parametrize(
    "ts_round, now_min, expected_anchor_min",
    [
        ("nearest", 1, 0),
        ("nearest", 16, 30),
        ("nearest", 15, 0),  # exact tie -> even multiple (NOW // 30 min is even)
        ("nearest", 45, 60),
        ("first", 29, 0),
        ("last", 1, 30),
        ("last", 0, 0),
    ],
)
def test_grid_anchor_matches_emhass_rounding(ts_round, now_min, expected_anchor_min):
    now = NOW + timedelta(minutes=now_min)
    assert grid_anchor(now, 30, ts_round) == NOW + timedelta(
        minutes=expected_anchor_min
    )


def test_grid_anchor_rejects_unknown_mode():
    with pytest.raises(ValueError):
        grid_anchor(NOW, 30, "round")


def test_deadline_just_past_a_boundary_never_overshoots():
    # now 12:01, deadline 13:01: two 30-min slots must end by 13:00 whatever the anchor
    d = make_demand(
        deadline=NOW + timedelta(hours=1, minutes=1),
        window_start=None,
        expires_at=NOW + timedelta(hours=2),
    )
    for ts_round, anchor_min in (("nearest", 0), ("last", 30), ("first", 0)):
        payload, mapping = build_runtimeparams(
            [d], now=NOW + timedelta(minutes=1), extra={}, ts_round=ts_round, **CFG
        )
        end = payload["end_timesteps_of_each_deferrable_load"][0]
        assert NOW + timedelta(minutes=anchor_min + 30 * end) <= d.deadline
        assert payload["operating_timesteps_of_each_deferrable_load"][0] <= end


def test_future_window_start_is_anchored():
    d = make_demand(
        window_start=NOW + timedelta(minutes=46),
        deadline=NOW + timedelta(hours=4),
        expires_at=NOW + timedelta(hours=5),
    )
    payload, _ = build_runtimeparams(
        [d], now=NOW + timedelta(minutes=1), extra={}, ts_round="nearest", **CFG
    )
    # anchor 12:00, 12:46 -> ceil to 13:00 = step 2
    assert payload["start_timesteps_of_each_deferrable_load"] == [2]
