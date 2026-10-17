#!/usr/bin/env python3
"""Classify known EMHASS failure signatures in action_logs.txt (or logger_emhass.log).

Each signature class carries the exact logger strings from EMHASS v0.18.6
(src/emhass/forecast.py, command_line.py, optimization.py, retrieve_hass.py,
web_server.py, utils.py), a severity and a one-line hint. The scanner counts
matches per class with first/last line numbers (and timestamps when the log
has them) and exits 1 when any ERROR class fired.

Line formats accepted:
    action_logs.txt   : "<LEVEL> - <logger> - <message>"            (web_server)
    logger_emhass.log : "<asctime> - <logger> - <LEVEL> - <message>" (utils.get_logger)
    anything else     : treated as a message with unknown level

Usage:
    scan_logs.py <action_logs.txt> [--since 24h] [--now "YYYY-MM-DD HH:MM:SS"] [--json]
    scan_logs.py --list

Exit codes: 0 no ERROR class, 1 at least one ERROR class, 2 file unreadable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

CACHE_MISS_STORM_THRESHOLD = 3  # more MISS lines than this in the window = storm


@dataclass
class Signature:
    id: str
    severity: str  # ERROR | WARN
    patterns: tuple[str, ...]  # regexes, matched case-sensitively against the message
    hint: str
    source: str  # upstream file(s) the strings come from


# Strings quoted from EMHASS v0.18.6. Keep them verbatim; regex-escape where needed.
SIGNATURES: tuple[Signature, ...] = (
    Signature(
        "infeasible",
        "ERROR",
        (
            r"Optimization failed with status: '",
            r"Cost function cannot be evaluated or Infeasible/Unbounded",
            r"Relaxed optimization also failed with status: ",
            r"Relaxed optimization crashed: ",
        ),
        "Solver found no feasible plan: check SOC targets vs capacity, operating hours vs window, "
        "hybrid inverter limits (#875), grid limits; run emhass-config-validate on config.json.",
        "optimization.py",
    ),
    Signature(
        "relaxed",
        "WARN",
        (
            r"Solving relaxed problem \(LP\)\.\.\.",
            r"Relaxed optimization successful!",
            r"Retrying with relaxed constraints \(Continuous LP\)",
        ),
        "MILP infeasible, EMHASS published a relaxed LP (status 'Optimal (Relaxed)'): loads may run "
        "at partial power or in pieces. Find the constraint that broke (see 'infeasible').",
        "optimization.py",
    ),
    Signature(
        "nan_forecast",
        "ERROR",
        (
            r"forecast values must be finite real numbers",
            r"Load forecast rejected before optimization: ",
            r"ERROR: The passed data is either the wrong type or the length is not correct",
            r"Passed data from passed list is not long enough",
            r"Passed data from CSV is not long enough",
            r"ERROR: external PV P10 companion rejected: ",
            r"get_mix_forecast: .* NaN; skipping the mix-forecast blend",
        ),
        "A runtime forecast list contains NaN/null/str or is shorter than the horizon; EMHASS fails "
        "closed (#1135). Fix the producer of pv_power_forecast / load_cost_forecast / etc.",
        "utils.py, forecast.py",
    ),
    Signature(
        "missing_sensor",
        "ERROR",
        (
            r"was not found in DataFrame columns: ",
            r"prepare_data: the following configured sensor names were not found in the retrieved data",
            r"these columns still contain NaN values after cleaning: ",
            r"No data retrieved from ",
            r"Unable to access Home Assistant instance, TOKEN/KEY is invalid or missing",
            r"Network error connecting to Home Assistant: ",
            r"Unable to obtain configuration from Home Assistant at: ",
            r"No data found in VictoriaMetrics for entity: ",
            r"Entity '.*' not found in any InfluxDB measurement",
        ),
        "A configured sensor returned no history: check the entity id in config.json, that it has "
        "numeric state history for historic_days_to_retrieve days, and the HA token / URL.",
        "retrieve_hass.py",
    ),
    Signature(
        "solcast_quota",
        "ERROR",
        (
            r"Solcast error: May have exceeded your subscription limit\.",
            r"Solcast daily API call limit reached \(safety cap\)",
            r"Solcast error: Issue with request, check API key and rooftop ID\.",
            r"No data retrieved from Solcast service\.",
            r"The solcast_api_key parameter was not defined",
            r"The solcast_rooftop_id parameter was not defined",
        ),
        "Solcast returned 402/429 or the local safety cap hit: fewer calls per day (use "
        "weather_forecast_cache + weather_forecast_cache_only), check API key / rooftop id.",
        "forecast.py",
    ),
    Signature(
        "runtime_400",
        "ERROR",
        (
            r"Error parsing runtime params JSON: ",
            r"Check your payload for syntax errors \(e\.g\., use 'false' instead of 'False'\)",
            r"Home Assistant returned 400 Bad Request\. URL: ",
            r"ERROR: passed action is not valid",
            r"The passed action set_type parameter '.*' is not valid",
            r"params\.pkl is corrupted or truncated \(race condition\); cannot proceed",
            r"Unable to find params\.pkl file",
        ),
        "The POST /action payload or action name was rejected: send valid JSON (true/false, no "
        "trailing commas), a known action, and save the config once so params.pkl exists.",
        "web_server.py, retrieve_hass.py, command_line.py",
    ),
    Signature(
        "websocket",
        "WARN",
        (
            r"WebSocket data retrieval failed, falling back to REST API",
            r"WebSocket connection timed out",
            r"Websocket connection error: ",
            r"Failed to get data via WebSocket: ",
            r"WebSocket connection failed: ",
            r"WebSocket shutdown failed: ",
        ),
        "use_websocket=true but the HA websocket dropped; EMHASS fell back to REST (slower, same "
        "data). Persistent: set use_websocket=false or check the HA URL / token / proxy.",
        "retrieve_hass.py, web_server.py",
    ),
    Signature(
        "cache_miss_storm",
        "WARN",
        (r"OptimizationCache MISS: ",),
        "The cached optimization problem is rebuilt every call: a plant_conf/optim_conf value changes "
        "between calls (runtime override toggling?). Pin it or pass it as a runtime key.",
        "command_line.py (DEBUG level; needs logging_level=DEBUG)",
    ),
    Signature(
        "weather_cache",
        "WARN",
        (
            r"Cache file is corrupt or empty\.",
            r"Cache does not fully cover the requested timeframe\.",
            r"Solcast cache file missing or deleted due to being out of date\.",
            r"Open-Meteo covariate cache is unreadable; refetching",
        ),
        "Weather cache stale or corrupt: run the weather-forecast-cache action once "
        "(it refetches), then keep weather_forecast_cache_only for the MPC calls.",
        "forecast.py",
    ),
    Signature(
        "mpc_horizon",
        "ERROR",
        (
            r"Set the MPC prediction horizon to at least 5 times the optimization time step",
            r"MPC Prediction Horizon \(\d+\) does not match the initialized optimization window",
        ),
        "prediction_horizon is too short or changed between calls; pass >= 5 steps and keep it "
        "constant (a change rebuilds the problem).",
        "optimization.py",
    ),
    Signature(
        "deferrable_padding",
        "WARN",
        (
            r": padded from \d+ to \d+ entries to match number_of_deferrable_loads=",
            r": a None/null entry was replaced with the parameter default \(number_of_deferrable_loads=",
            r"has \d+ entries but number_of_batteries=",
        ),
        "A per-load or per-battery array does not match number_of_deferrable_loads / "
        "number_of_batteries; run emhass-config-validate and fix the lengths.",
        "utils.py",
    ),
)

# Run / publish markers (command_line.py) for the cycle count.
RUN_MARKER = "Setting up needed data"
PUBLISH_MARKER = "Publishing data to HASS instance"

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})(?:[.,](\d+))?")


@dataclass
class ClassResult:
    id: str
    severity: str
    hint: str
    count: int = 0
    first_line: int | None = None
    last_line: int | None = None
    first_ts: str | None = None
    last_ts: str | None = None


@dataclass
class Report:
    classes: list[ClassResult]
    samples: dict[str, list[str]] = field(default_factory=dict)
    runs: int = 0
    publishes: int = 0
    lines_scanned: int = 0
    lines_in_window: int = 0
    has_error: bool = False
    notes: list[str] = field(default_factory=list)


def parse_since(spec: str) -> int:
    """'24h' / '90m' / '2d' / '30s' -> seconds."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd])\s*", spec or "")
    if not m:
        raise ValueError(f"--since must look like 24h, 90m, 2d or 30s, got {spec!r}")
    factor = {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    return int(float(m.group(1)) * factor)


def parse_line(line: str) -> tuple[datetime | None, str | None, str]:
    """Return (timestamp, level, message) for either EMHASS log format."""
    ts = None
    rest = line.rstrip("\r\n")
    m = _TS_RE.match(rest)
    if m:
        try:
            ts = datetime.fromisoformat(m.group(1).replace("T", " "))
        except ValueError:
            ts = None
        rest = rest[m.end() :].lstrip(" -")
    level = None
    parts = rest.split(" - ", 2)
    if parts and parts[0] in LEVELS:
        level = parts[0]
        rest = parts[2] if len(parts) == 3 else (parts[1] if len(parts) == 2 else "")
    elif len(parts) >= 2 and parts[1] in LEVELS:
        level = parts[1]
        rest = parts[2] if len(parts) == 3 else ""
    return ts, level, rest


def scan(lines, since: str | None = None, now: datetime | None = None) -> Report:
    compiled = [(sig, [re.compile(p) for p in sig.patterns]) for sig in SIGNATURES]
    results = {
        sig.id: ClassResult(sig.id, sig.severity, sig.hint) for sig in SIGNATURES
    }
    results["unclassified_error"] = ClassResult(
        "unclassified_error",
        "ERROR",
        "ERROR line not in the signature catalogue; read it verbatim and check the EMHASS issues.",
    )
    report = Report(classes=[])
    cutoff = None
    if since:
        cutoff = (now or datetime.now()) - timedelta(seconds=parse_since(since))
    saw_ts = False

    for lineno, raw in enumerate(lines, start=1):
        report.lines_scanned += 1
        ts, level, msg = parse_line(raw)
        if ts is not None:
            saw_ts = True
        if cutoff is not None and ts is not None and ts < cutoff:
            continue
        report.lines_in_window += 1
        if RUN_MARKER in msg:
            report.runs += 1
        if PUBLISH_MARKER in msg:
            report.publishes += 1
        matched = False
        for sig, regexes in compiled:
            if any(r.search(msg) for r in regexes):
                _hit(results[sig.id], report, lineno, ts, msg)
                matched = True
        if not matched and level == "ERROR":
            _hit(results["unclassified_error"], report, lineno, ts, msg)

    storm = results["cache_miss_storm"]
    if storm.count and storm.count <= CACHE_MISS_STORM_THRESHOLD:
        storm.count = 0
        report.samples.pop("cache_miss_storm", None)

    if cutoff is not None and not saw_ts:
        report.notes.append(
            "--since ignored: this log has no timestamps (action_logs.txt is written without them; "
            "EMHASS truncates it per action, so it already covers only the latest run)"
        )
    report.classes = list(results.values())
    report.has_error = any(c.count and c.severity == "ERROR" for c in report.classes)
    return report


def _hit(
    result: ClassResult, report: Report, lineno: int, ts: datetime | None, msg: str
) -> None:
    result.count += 1
    if result.first_line is None:
        result.first_line = lineno
        result.first_ts = ts.isoformat(sep=" ") if ts else None
    result.last_line = lineno
    result.last_ts = ts.isoformat(sep=" ") if ts else None
    samples = report.samples.setdefault(result.id, [])
    if len(samples) < 3:
        samples.append(msg)


def render(report: Report) -> str:
    out: list[str] = []
    fired = [c for c in report.classes if c.count]
    out.append(
        f"scanned {report.lines_scanned} lines ({report.lines_in_window} in window), "
        f"{report.runs} run(s) started, {report.publishes} publish(es)"
    )
    for note in report.notes:
        out.append(f"note: {note}")
    if not fired:
        out.append("OK: no known failure signatures found")
        return "\n".join(out)
    fired.sort(key=lambda c: (0 if c.severity == "ERROR" else 1, -c.count))
    for c in fired:
        where = f"lines {c.first_line}-{c.last_line}"
        if c.first_ts:
            where = f"{c.first_ts} .. {c.last_ts} ({where})"
        out.append(f"{c.severity:<5} {c.id}: {c.count}x, {where}")
        out.append(f"      hint: {c.hint}")
        for sample in report.samples.get(c.id, [])[:1]:
            out.append(f"      e.g.: {sample[:200]}")
    verdict = "FAIL" if report.has_error else "WARN"
    out.append(
        f"{verdict}: {sum(1 for c in fired if c.severity == 'ERROR')} error class(es), "
        f"{sum(1 for c in fired if c.severity == 'WARN')} warning class(es)"
    )
    return "\n".join(out)


def list_signatures() -> str:
    out = []
    for sig in SIGNATURES:
        out.append(f"{sig.severity:<5} {sig.id}  [{sig.source}]")
        for p in sig.patterns:
            out.append(f"      {p}")
        out.append(f"      hint: {sig.hint}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "logfile", nargs="?", help="action_logs.txt or logger_emhass.log"
    )
    parser.add_argument(
        "--since", help="only lines newer than this (24h, 90m, 2d); needs timestamps"
    )
    parser.add_argument(
        "--now", help="reference time for --since, 'YYYY-MM-DD HH:MM:SS' (default: now)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--list", action="store_true", help="print the signature catalogue and exit"
    )
    args = parser.parse_args(argv)

    if args.list:
        print(list_signatures())
        return 0
    if not args.logfile:
        parser.error("logfile is required unless --list is given")
    try:
        lines = (
            Path(args.logfile)
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        )
    except OSError as exc:
        print(f"ERROR: cannot read {args.logfile}: {exc}")
        return 2
    now = None
    if args.now:
        try:
            now = datetime.fromisoformat(args.now)
        except ValueError:
            print(f"ERROR: --now must be ISO-like, got {args.now!r}")
            return 2
    try:
        report = scan(lines, since=args.since, now=now)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(render(report))
    return 1 if report.has_error else 0


if __name__ == "__main__":
    sys.exit(main())
