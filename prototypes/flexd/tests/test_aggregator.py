from datetime import datetime, timedelta, timezone

from flexd.aggregator import build_runtimeparams
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
        0.6
    ]  # 1200 Wh / 2000 W
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
    assert payload["operating_hours_of_each_deferrable_load"] == [0.6]  # flexd wins
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
    assert payload["operating_hours_of_each_deferrable_load"] == [0.01]


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
    assert payload["operating_hours_of_each_deferrable_load"] == [
        0.16
    ]  # floor(0.1667*100)/100
