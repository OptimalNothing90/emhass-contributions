"""Tests for skills/emhass-anomaly/scripts/scan_logs.py.

Synthetic action_logs.txt built from the exact logger strings in EMHASS
v0.18.6 (forecast.py, command_line.py, optimization.py, retrieve_hass.py,
web_server.py, utils.py). action_logs.txt lines are
"<LEVEL> - <logger name> - <message>" (web_server._configure_logging); the
CLI/file logger adds a leading "%(asctime)s - " which the scanner must accept too.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "emhass-anomaly"
    / "scripts"
    / "scan_logs.py"
)

ACTION_LOG = """INFO - emhass.command_line - Setting up needed data
INFO - emhass.command_line - Performing naive MPC optimization
WARNING - emhass.optimization - Optimization failed with status: 'infeasible'. Retrying with relaxed constraints (Continuous LP)...
INFO - emhass.optimization - Solving relaxed problem (LP)...
INFO - emhass.optimization - Relaxed optimization successful!
INFO - emhass.command_line - Publishing data to HASS instance
INFO - emhass.command_line - Setting up needed data
ERROR - emhass.utils - ERROR: pv_power_forecast contains non-finite value nan at position 3; forecast values must be finite real numbers
ERROR - emhass.retrieve_hass - Variable 'sensor.power_load_no_var_loads' was not found in DataFrame columns: ['sensor.power_photovoltaics']. This is typically because no data could be retrieved from Home Assistant or InfluxDB. Error: 'sensor.power_load_no_var_loads'
ERROR - emhass.forecast - Solcast error: May have exceeded your subscription limit.
WARNING - emhass.forecast - Solcast daily API call limit reached (safety cap). Skipping live API call to preserve quota.
ERROR - emhass.web_server - Error parsing runtime params JSON: Expecting value: line 1 column 1 (char 0)
ERROR - emhass.web_server - Check your payload for syntax errors (e.g., use 'false' instead of 'False')
WARNING - emhass.retrieve_hass - WebSocket data retrieval failed, falling back to REST API
ERROR - emhass.retrieve_hass - WebSocket connection timed out
DEBUG - emhass.command_line - OptimizationCache MISS: Config changed - plant_conf_hash
DEBUG - emhass.command_line - OptimizationCache MISS: Config changed - plant_conf_hash
DEBUG - emhass.command_line - OptimizationCache MISS: Config changed - optim_conf_structural_hash
DEBUG - emhass.command_line - OptimizationCache MISS: Config changed - plant_conf_hash
WARNING - emhass.optimization - Cost function cannot be evaluated or Infeasible/Unbounded
INFO - emhass.command_line - Publishing data to HASS instance
"""

TIMESTAMPED_LOG = """2026-10-17 06:00:01,123 - emhass.command_line - INFO - Setting up needed data
2026-10-17 06:00:05,456 - emhass.forecast - ERROR - Solcast error: May have exceeded your subscription limit.
2026-10-17 06:30:02,000 - emhass.forecast - ERROR - Solcast error: May have exceeded your subscription limit.
2026-10-17 07:00:03,000 - emhass.retrieve_hass - WARNING - WebSocket data retrieval failed, falling back to REST API
"""

CLEAN_LOG = """INFO - emhass.command_line - Setting up needed data
INFO - emhass.command_line - Performing naive MPC optimization
INFO - emhass.optimization - Perform an iteration of a naive MPC controller
INFO - emhass.command_line - Publishing data to HASS instance
"""


@pytest.fixture
def log_file(tmp_path):
    p = tmp_path / "action_logs.txt"
    p.write_text(ACTION_LOG, encoding="utf-8")
    return p


def _classes(report):
    return {c.id: c for c in report.classes if c.count}


# -------------------------------------------------------------- classification


def test_every_known_signature_is_classified(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines())
    ids = set(_classes(report))
    assert {
        "infeasible",
        "relaxed",
        "nan_forecast",
        "missing_sensor",
        "solcast_quota",
        "runtime_400",
        "websocket",
        "cache_miss_storm",
    } <= ids


def test_counts_and_line_numbers(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines())
    c = _classes(report)
    assert c["solcast_quota"].count == 2
    assert c["cache_miss_storm"].count == 4
    assert c["infeasible"].first_line == 3
    assert c["infeasible"].last_line == 20


def test_each_class_has_severity_and_hint(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines())
    for c in _classes(report).values():
        assert c.severity in ("ERROR", "WARN")
        assert c.hint and len(c.hint) < 240


def test_error_classes_are_errors_and_relaxed_is_warn(scan_logs_mod):
    c = _classes(scan_logs_mod.scan(ACTION_LOG.splitlines()))
    assert c["infeasible"].severity == "ERROR"
    assert c["nan_forecast"].severity == "ERROR"
    assert c["missing_sensor"].severity == "ERROR"
    assert c["solcast_quota"].severity == "ERROR"
    assert c["runtime_400"].severity == "ERROR"
    assert c["relaxed"].severity == "WARN"
    assert c["websocket"].severity == "WARN"


def test_cache_miss_below_threshold_is_not_a_storm(scan_logs_mod):
    lines = [
        "DEBUG - emhass.command_line - OptimizationCache MISS: Empty cache, building new optimization"
    ]
    report = scan_logs_mod.scan(lines)
    assert "cache_miss_storm" not in _classes(report)


def test_unclassified_error_lines_are_collected(scan_logs_mod):
    lines = ["ERROR - emhass.something - a brand new failure nobody catalogued"]
    report = scan_logs_mod.scan(lines)
    assert "unclassified_error" in _classes(report)
    assert report.samples["unclassified_error"][0].endswith("catalogued")


def test_clean_log_has_no_findings(scan_logs_mod):
    report = scan_logs_mod.scan(CLEAN_LOG.splitlines())
    assert _classes(report) == {}
    assert report.has_error is False


def test_sample_line_is_kept_per_class(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines())
    assert "subscription limit" in report.samples["solcast_quota"][0]


# ---------------------------------------------------------------- timestamps


def test_timestamped_lines_give_first_last_timestamps(scan_logs_mod):
    report = scan_logs_mod.scan(TIMESTAMPED_LOG.splitlines())
    c = _classes(report)["solcast_quota"]
    assert c.first_ts.startswith("2026-10-17 06:00:05")
    assert c.last_ts.startswith("2026-10-17 06:30:02")


def test_since_filters_timestamped_lines(scan_logs_mod):
    from datetime import datetime

    now = datetime(2026, 10, 17, 7, 10, 0)
    report = scan_logs_mod.scan(TIMESTAMPED_LOG.splitlines(), since="1h", now=now)
    c = _classes(report)
    assert c["solcast_quota"].count == 1  # only the 06:30 one is within 1 h
    assert c["websocket"].count == 1


def test_since_on_untimestamped_log_is_noted_not_fatal(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines(), since="24h")
    assert any("timestamp" in n for n in report.notes)
    assert _classes(report)["solcast_quota"].count == 2


@pytest.mark.parametrize(
    "spec,seconds", [("24h", 86400), ("90m", 5400), ("2d", 172800), ("30s", 30)]
)
def test_parse_since(scan_logs_mod, spec, seconds):
    assert scan_logs_mod.parse_since(spec) == seconds


def test_parse_since_rejects_garbage(scan_logs_mod):
    with pytest.raises(ValueError):
        scan_logs_mod.parse_since("yesterday")


# ------------------------------------------------------------- run counting


def test_runs_are_counted_from_setup_lines(scan_logs_mod):
    report = scan_logs_mod.scan(ACTION_LOG.splitlines())
    assert report.runs == 2
    assert report.publishes == 2


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


def test_cli_exit_one_on_error_class(log_file):
    proc = _run_cli(log_file)
    assert proc.returncode == 1
    assert "infeasible" in proc.stdout
    assert "hint" in proc.stdout.lower()


def test_cli_exit_zero_on_clean_log(tmp_path):
    p = tmp_path / "action_logs.txt"
    p.write_text(CLEAN_LOG, encoding="utf-8")
    proc = _run_cli(p)
    assert proc.returncode == 0, proc.stdout
    assert "no known failure signatures" in proc.stdout.lower()


def test_cli_json_output(log_file):
    proc = _run_cli(log_file, "--json")
    data = json.loads(proc.stdout)
    assert data["has_error"] is True
    assert any(c["id"] == "solcast_quota" and c["count"] == 2 for c in data["classes"])


def test_cli_since_flag(tmp_path):
    p = tmp_path / "logger_emhass.log"
    p.write_text(TIMESTAMPED_LOG, encoding="utf-8")
    proc = _run_cli(p, "--since", "1h", "--now", "2026-10-17 07:10:00")
    assert proc.returncode == 1
    assert "solcast_quota" in proc.stdout


def test_cli_missing_file_exits_two(tmp_path):
    assert _run_cli(tmp_path / "nope.txt").returncode == 2


def test_cli_list_signatures():
    proc = _run_cli("--list")
    assert proc.returncode == 0
    assert "infeasible" in proc.stdout and "Solcast" in proc.stdout


def test_render_orders_error_classes_by_first_appearance(scan_logs_mod):
    text = scan_logs_mod.render(scan_logs_mod.scan(ACTION_LOG.splitlines()))
    order = [
        cls
        for cls in ("infeasible", "nan_forecast", "missing_sensor", "solcast_quota")
        if f"ERROR {cls}:" in text
    ]
    assert order == ["infeasible", "nan_forecast", "missing_sensor", "solcast_quota"]
    assert (
        text.index("ERROR infeasible:")
        < text.index("ERROR nan_forecast:")
        < text.index("ERROR solcast_quota:")
    )
    assert text.index("ERROR solcast_quota:") < text.index("WARN  relaxed:")
