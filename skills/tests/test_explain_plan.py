"""Tests for skills/emhass-plan-explain/scripts/explain_plan.py.

Synthetic plan: 8 half-hour steps, one deferrable load that runs 2 steps in the
two cheapest hours, one battery that charges at night and discharges in the
evening. The shape mirrors GET /api/v1/plan at v0.18.6 (plan_store.serialize).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "emhass-plan-explain"
    / "scripts"
    / "explain_plan.py"
)

PRICES = [0.30, 0.10, 0.12, 0.25, 0.28, 0.35, 0.40, 0.20]
PV = [0, 0, 0, 500, 1500, 1200, 300, 0]
LOAD = [400, 400, 400, 600, 800, 1000, 900, 500]
DEF0 = [0, 3000, 3000, 0, 0, 0, 0, 0]
BATT = [0, -1000, -1000, 0, 0, 1000, 1000, 0]  # <0 charge, >0 discharge
SOC = [0.5, 0.6, 0.7, 0.7, 0.7, 0.6, 0.5, 0.5]


def _records(status="Optimal", with_prices=True, with_battery=True):
    recs = []
    for i in range(8):
        hh = i // 2
        mm = 30 * (i % 2)
        rec = {
            "timestamp": f"2026-10-17T{hh:02d}:{mm:02d}:00.000Z",
            "P_PV": PV[i],
            "P_Load": LOAD[i],
            "P_deferrable0": DEF0[i],
            "P_grid_pos": max(0, LOAD[i] + DEF0[i] - PV[i] - BATT[i]),
            "P_grid_neg": -max(0, PV[i] + BATT[i] - LOAD[i] - DEF0[i]),
            "optim_status": status,
            "cost_profit": -0.01 * (i + 1),
        }
        rec["P_grid"] = rec["P_grid_pos"] + rec["P_grid_neg"]
        if with_prices:
            rec["unit_load_cost"] = PRICES[i]
            rec["unit_prod_price"] = 0.08
        if with_battery:
            rec["P_batt"] = BATT[i]
            rec["SOC_opt"] = SOC[i]
        recs.append(rec)
    return recs


def _plan(**kw):
    return {
        "status": "ok",
        "generated_at": "2026-10-16T23:55:00Z",
        "emhass_schema_version": "1.0",
        "plan": _records(**kw),
    }


@pytest.fixture
def plan_file(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(_plan()), encoding="utf-8")
    return p


# ---------------------------------------------------------------- parsing


def test_load_plan_accepts_api_envelope_and_bare_list(explain_plan_mod):
    env = explain_plan_mod.load_plan(_plan())
    bare = explain_plan_mod.load_plan(_records())
    assert len(env.records) == len(bare.records) == 8
    assert env.generated_at == "2026-10-16T23:55:00Z"


def test_no_run_envelope_is_reported(explain_plan_mod):
    plan = explain_plan_mod.load_plan(
        {
            "status": "no-run",
            "generated_at": None,
            "emhass_schema_version": None,
            "plan": None,
        }
    )
    assert plan.records == []
    text = explain_plan_mod.render(explain_plan_mod.analyze(plan))
    assert "no-run" in text


def test_timestep_minutes_derived_from_timestamps(explain_plan_mod):
    plan = explain_plan_mod.load_plan(_plan())
    assert explain_plan_mod.analyze(plan).step_minutes == 30


# -------------------------------------------------------- deferrable loads


def test_deferrable_summary_has_run_window_and_energy(explain_plan_mod):
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()))
    d = summary.deferrables[0]
    assert d.index == 0
    assert d.on_steps == 2
    assert d.runs == [(1, 2)]  # contiguous step indices
    assert d.energy_kwh == pytest.approx(3.0)  # 3000 W * 2 * 0.5 h
    assert d.first_on == "00:30"
    assert d.last_off == "01:30"


def test_deferrable_never_runs_is_flagged(explain_plan_mod):
    recs = _records()
    for r in recs:
        r["P_deferrable0"] = 0
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(recs))
    assert summary.deferrables[0].on_steps == 0
    text = explain_plan_mod.render(summary)
    assert "never" in text.lower()


def test_cheapest_hours_reasoning_when_prices_present(explain_plan_mod):
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()))
    d = summary.deferrables[0]
    assert d.in_cheapest_window is True
    assert d.avg_price_on == pytest.approx(0.11)
    assert d.avg_price_all == pytest.approx(sum(PRICES) / 8)


def test_cheaper_unused_steps_are_listed(explain_plan_mod):
    recs = _records()
    # move the load to the two most expensive steps
    for r in recs:
        r["P_deferrable0"] = 0
    recs[5]["P_deferrable0"] = 3000
    recs[6]["P_deferrable0"] = 3000
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(recs))
    d = summary.deferrables[0]
    assert d.in_cheapest_window is False
    assert d.cheaper_unused_steps[:2] == [1, 2]


def test_no_price_columns_disables_price_reasoning(explain_plan_mod):
    summary = explain_plan_mod.analyze(
        explain_plan_mod.load_plan(_plan(with_prices=False))
    )
    assert summary.deferrables[0].in_cheapest_window is None
    assert (
        "price" not in explain_plan_mod.render(summary).lower().split("deferrable")[0]
    )


# -------------------------------------------------------- config window check


def test_config_window_and_expected_steps_compare(explain_plan_mod):
    cfg = {
        "optimization_time_step": 30,
        "number_of_deferrable_loads": 1,
        "operating_hours_of_each_deferrable_load": [2],
        "start_timesteps_of_each_deferrable_load": [0],
        "end_timesteps_of_each_deferrable_load": [4],
    }
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()), config=cfg)
    d = summary.deferrables[0]
    assert d.expected_steps == 4
    assert d.window == (0, 4)
    assert d.window_clamped is False
    assert any("4" in n and "2" in n for n in d.notes)  # fewer steps than configured


def test_config_window_beyond_horizon_is_clamped(explain_plan_mod):
    cfg = {
        "optimization_time_step": 30,
        "number_of_deferrable_loads": 1,
        "operating_hours_of_each_deferrable_load": [1],
        "start_timesteps_of_each_deferrable_load": [0],
        "end_timesteps_of_each_deferrable_load": [40],
    }
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()), config=cfg)
    assert summary.deferrables[0].window_clamped is True


def test_run_outside_configured_window_is_noted(explain_plan_mod):
    cfg = {
        "optimization_time_step": 30,
        "number_of_deferrable_loads": 1,
        "operating_hours_of_each_deferrable_load": [1],
        "start_timesteps_of_each_deferrable_load": [4],
        "end_timesteps_of_each_deferrable_load": [8],
    }
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()), config=cfg)
    assert any("outside" in n for n in summary.deferrables[0].notes)


# ---------------------------------------------------------------- battery


def test_battery_summary(explain_plan_mod):
    b = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan())).batteries[0]
    assert b.charge_kwh == pytest.approx(1.0)
    assert b.discharge_kwh == pytest.approx(1.0)
    assert b.soc_start == 0.5 and b.soc_end == 0.5
    assert b.soc_min == 0.5 and b.soc_max == 0.7
    assert b.charge_steps == [1, 2]
    assert b.discharge_steps == [5, 6]


def test_battery_grid_charging_is_detected(explain_plan_mod):
    b = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan())).batteries[0]
    assert b.grid_charge_steps == [1, 2]  # PV is 0 while charging


def test_multi_battery_columns(explain_plan_mod):
    recs = _records(with_battery=False)
    for i, r in enumerate(recs):
        r["P_batt"] = BATT[i] * 2
        r["P_batt_0"] = BATT[i]
        r["P_batt_1"] = BATT[i]
        r["SOC_opt_0"] = SOC[i]
        r["SOC_opt_1"] = SOC[i]
    summary = explain_plan_mod.analyze(explain_plan_mod.load_plan(recs))
    assert [b.index for b in summary.batteries] == [0, 1]


def test_no_battery_columns_means_no_battery_section(explain_plan_mod):
    summary = explain_plan_mod.analyze(
        explain_plan_mod.load_plan(_plan(with_battery=False))
    )
    assert summary.batteries == []


# ------------------------------------------------------------- status / grid


def test_non_optimal_status_is_surfaced_first(explain_plan_mod):
    summary = explain_plan_mod.analyze(
        explain_plan_mod.load_plan(_plan(status="Infeasible"))
    )
    assert summary.optim_status == "Infeasible"
    text = explain_plan_mod.render(summary)
    assert text.splitlines()[0].startswith("STATUS")
    assert "Infeasible" in text.splitlines()[0]


def test_relaxed_status_is_explained(explain_plan_mod):
    summary = explain_plan_mod.analyze(
        explain_plan_mod.load_plan(_plan(status="Optimal (Relaxed)"))
    )
    assert "relaxed" in explain_plan_mod.render(summary).lower()


def test_grid_totals(explain_plan_mod):
    g = explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan())).grid
    assert g.import_kwh > 0
    assert g.export_kwh >= 0
    assert g.peak_import_w == 4400  # step 1: 400 + 3000 + 1000 charge, PV 0


# ------------------------------------------------------------- last-run


def test_last_run_is_merged(explain_plan_mod):
    last = {
        "status": "ok",
        "timestamp": "2026-10-16T23:55:00Z",
        "action": "naive-mpc-optim",
        "stage_times": {"optim_solve": 1.2, "publish": 0.1},
        "duration_total_seconds": 2.5,
        "emhass_version": "0.18.6",
        "schema_version": "1.0",
        "infeasible": False,
        "error_message": None,
    }
    summary = explain_plan_mod.analyze(
        explain_plan_mod.load_plan(_plan()), last_run=last
    )
    text = explain_plan_mod.render(summary)
    assert "naive-mpc-optim" in text and "2.5" in text


def test_last_run_error_message_is_shown(explain_plan_mod):
    last = {
        "status": "error",
        "action": "dayahead-optim",
        "error_message": "solver exploded",
    }
    text = explain_plan_mod.render(
        explain_plan_mod.analyze(explain_plan_mod.load_plan(_plan()), last_run=last)
    )
    assert "solver exploded" in text


# ------------------------------------------------------------------- CLI


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_cli_prints_summary(plan_file):
    proc = _run_cli(plan_file)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Deferrable load 0" in proc.stdout
    assert "Battery" in proc.stdout


def test_cli_json_output(plan_file):
    proc = _run_cli(plan_file, "--json")
    data = json.loads(proc.stdout)
    assert data["deferrables"][0]["on_steps"] == 2


def test_cli_exit_one_when_status_not_optimal(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(_plan(status="Infeasible")), encoding="utf-8")
    assert _run_cli(p).returncode == 1


def test_cli_missing_file_exits_two(tmp_path):
    assert _run_cli(tmp_path / "nope.json").returncode == 2
