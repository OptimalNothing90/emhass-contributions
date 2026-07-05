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
    assert payload["def_total_hours"] == [0.6]  # 1200 Wh / 2000 W
    assert payload["start_timesteps_of_each_deferrable_load"] == [0]
    assert payload["end_timesteps_of_each_deferrable_load"] == [8]  # 4h / 30min
    assert payload["def_current_power"] == [0]
    assert payload["prediction_horizon"] == 48
    assert mapping == {"dishwasher": {"slot": 0, "clamped": False}}


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
        [d], now=NOW, extra={"soc_init": 0.5, "def_total_hours": [99]}, **CFG
    )
    assert payload["soc_init"] == 0.5
    assert payload["def_total_hours"] == [0.6]  # flexd key wins


def test_current_power_passthrough():
    d = make_demand(
        current_power_w=1500,
        deadline=NOW + timedelta(hours=4),
        expires_at=NOW + timedelta(hours=5),
    )
    payload, _ = build_runtimeparams([d], now=NOW, extra={}, **CFG)
    assert payload["def_current_power"] == [1500]
