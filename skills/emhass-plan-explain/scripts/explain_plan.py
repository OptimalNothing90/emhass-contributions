#!/usr/bin/env python3
"""Explain an EMHASS plan (GET /api/v1/plan) in plain language.

Reads the plan JSON from a file or URL, optionally the /api/v1/last-run JSON
and the config.json the plan was made with, and prints one paragraph per
deferrable load and battery: when it runs, how many timesteps, energy, whether
the configured window was clamped, whether the solver status was Optimal, and
a cheapest-hours check from the price columns when present.

Stdlib only. Column names follow the opt_res DataFrame at EMHASS v0.18.6
(P_deferrable{k}, P_batt / P_batt_{k}, SOC_opt / SOC_opt_{k}, P_grid_pos,
P_grid_neg, P_PV, P_Load, unit_load_cost, unit_prod_price, optim_status,
cost_profit). P_batt > 0 is discharge, < 0 is charge.

Usage:
    explain_plan.py <plan.json|http://host:5000/api/v1/plan>
                    [--last-run <last_run.json|URL>] [--config config.json]
                    [--tz Europe/Berlin] [--json]

Exit codes: 0 plan is Optimal (incl. Optimal_Inaccurate / Optimal (Relaxed)),
1 plan status is not optimal or no run yet, 2 input unreadable.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

OK_STATUSES = ("Optimal", "Optimal_Inaccurate", "Optimal (Relaxed)")
ON_THRESHOLD_W = 1.0  # a deferrable load with P below this is "off"


@dataclass
class Plan:
    records: list[dict]
    status: str | None = None
    generated_at: str | None = None
    schema_version: str | None = None


@dataclass
class DeferrableSummary:
    index: int
    on_steps: int = 0
    runs: list[tuple[int, int]] = field(default_factory=list)
    energy_kwh: float = 0.0
    peak_w: float = 0.0
    first_on: str | None = None
    last_off: str | None = None
    in_cheapest_window: bool | None = None
    avg_price_on: float | None = None
    avg_price_all: float | None = None
    cheaper_unused_steps: list[int] = field(default_factory=list)
    expected_steps: int | None = None
    window: tuple[int, int] | None = None
    window_clamped: bool | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class BatterySummary:
    index: int
    charge_kwh: float = 0.0
    discharge_kwh: float = 0.0
    soc_start: float | None = None
    soc_end: float | None = None
    soc_min: float | None = None
    soc_max: float | None = None
    charge_steps: list[int] = field(default_factory=list)
    discharge_steps: list[int] = field(default_factory=list)
    grid_charge_steps: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class GridSummary:
    import_kwh: float = 0.0
    export_kwh: float = 0.0
    peak_import_w: float = 0.0
    pv_kwh: float = 0.0
    load_kwh: float = 0.0
    cost_total: float | None = None


@dataclass
class Summary:
    n_steps: int
    step_minutes: int | None
    optim_status: str | None
    generated_at: str | None
    schema_version: str | None
    horizon_hours: float | None
    first_step: str | None
    last_step: str | None
    deferrables: list[DeferrableSummary]
    batteries: list[BatterySummary]
    grid: GridSummary
    last_run: dict | None
    notes: list[str]
    tz: str = "UTC"


# --------------------------------------------------------------------------- input


def _read_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=15) as resp:
            return resp.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def load_plan(obj) -> Plan:
    """Accept the /api/v1/plan envelope, a bare record list, a path or a URL."""
    if isinstance(obj, (str, Path)):
        obj = json.loads(_read_source(str(obj)))
    if isinstance(obj, list):
        return Plan(records=obj)
    if isinstance(obj, dict):
        records = obj.get("plan")
        return Plan(
            records=list(records) if isinstance(records, list) else [],
            status=obj.get("status"),
            generated_at=obj.get("generated_at"),
            schema_version=obj.get("emhass_schema_version"),
        )
    raise TypeError("plan must be a JSON object or list")


def load_json(source: str) -> dict:
    data = json.loads(_read_source(source))
    if not isinstance(data, dict):
        raise TypeError(f"{source}: expected a JSON object")
    return data


# ------------------------------------------------------------------------- helpers


def _num(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _col(records: list[dict], name: str) -> list[float | None]:
    return [_num(r.get(name)) for r in records]


def _parse_ts(value) -> datetime | None:
    if isinstance(value, (int, float)):
        # pandas to_json may emit epoch milliseconds
        return datetime.fromtimestamp(value / 1000.0, tz=UTC)
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _fmt_time(dt: datetime | None, tz=None) -> str | None:
    if dt is None:
        return None
    if tz is not None:
        dt = dt.astimezone(tz)
    return dt.strftime("%H:%M")


def _runs(on: list[bool]) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, flag in enumerate(on + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


# ------------------------------------------------------------------------- analysis


def analyze(
    plan: Plan, config: dict | None = None, last_run: dict | None = None, tz=None
) -> Summary:
    records = plan.records
    n = len(records)
    notes: list[str] = []
    if n == 0:
        return Summary(
            n_steps=0,
            step_minutes=None,
            optim_status=None,
            generated_at=plan.generated_at,
            schema_version=plan.schema_version,
            horizon_hours=None,
            first_step=None,
            last_step=None,
            deferrables=[],
            batteries=[],
            grid=GridSummary(),
            last_run=last_run,
            notes=[
                f"plan status is {plan.status or 'empty'}: no optimization run recorded yet"
            ],
        )

    stamps = [_parse_ts(r.get("timestamp")) for r in records]
    step_minutes = None
    if n > 1 and stamps[0] and stamps[1]:
        step_minutes = round((stamps[1] - stamps[0]).total_seconds() / 60)
    if step_minutes is None and config:
        step_minutes = config.get("optimization_time_step")
    dt_h = (step_minutes / 60.0) if step_minutes else None
    if dt_h is None:
        notes.append(
            "timestep unknown (no timestamps, no config); energies not computed"
        )
    energy = (
        (lambda watts: sum(w for w in watts if w) * dt_h / 1000.0)
        if dt_h
        else (lambda watts: 0.0)
    )

    status = next(
        (r.get("optim_status") for r in records if r.get("optim_status")), None
    )

    prices = _col(records, "unit_load_cost")
    have_prices = any(p is not None for p in prices)
    pv = _col(records, "P_PV")
    load = _col(records, "P_Load")
    grid_pos = _col(records, "P_grid_pos")
    grid_neg = _col(records, "P_grid_neg")

    # ---- deferrable loads
    def_keys = sorted(
        {
            k
            for r in records
            for k in r
            if k.startswith("P_deferrable") and k[len("P_deferrable") :].isdigit()
        },
        key=lambda k: int(k[len("P_deferrable") :]),
    )
    deferrables: list[DeferrableSummary] = []
    for key in def_keys:
        k = int(key[len("P_deferrable") :])
        power = _col(records, key)
        on = [(p or 0.0) > ON_THRESHOLD_W for p in power]
        d = DeferrableSummary(index=k, on_steps=sum(on), runs=_runs(on))
        d.energy_kwh = energy([p for p, flag in zip(power, on) if flag])
        d.peak_w = max((p for p in power if p), default=0.0)
        if d.on_steps:
            first = d.runs[0][0]
            last = d.runs[-1][1]
            d.first_on = _fmt_time(stamps[first], tz)
            if stamps[last] and step_minutes:
                d.last_off = _fmt_time(
                    stamps[last] + timedelta(minutes=step_minutes), tz
                )
        if have_prices:
            valid = [(i, p) for i, p in enumerate(prices) if p is not None]
            d.avg_price_all = sum(p for _, p in valid) / len(valid) if valid else None
            on_prices = [p for i, p in valid if on[i]]
            if on_prices:
                d.avg_price_on = sum(on_prices) / len(on_prices)
                cheapest = {
                    i for i, _ in sorted(valid, key=lambda ip: ip[1])[: d.on_steps]
                }
                on_set = {i for i in range(n) if on[i]}
                d.in_cheapest_window = on_set <= cheapest
                max_on = max(on_prices)
                d.cheaper_unused_steps = [
                    i
                    for i, p in sorted(valid, key=lambda ip: ip[1])
                    if not on[i] and p < max_on
                ]
        if config:
            _apply_config_to_deferrable(d, config, n, step_minutes)
        deferrables.append(d)

    # ---- batteries
    batteries: list[BatterySummary] = []
    batt_keys = sorted(
        {
            k
            for r in records
            for k in r
            if k.startswith("P_batt_") and k[len("P_batt_") :].isdigit()
        },
        key=lambda k: int(k[len("P_batt_") :]),
    )
    batt_cols = [
        (int(k[len("P_batt_") :]), k, f"SOC_opt_{k[len('P_batt_') :]}")
        for k in batt_keys
    ]
    if not batt_cols and any("P_batt" in r for r in records):
        batt_cols = [(0, "P_batt", "SOC_opt")]
    for k, p_key, soc_key in batt_cols:
        power = _col(records, p_key)
        soc = _col(records, soc_key)
        b = BatterySummary(index=k)
        b.charge_steps = [
            i for i, p in enumerate(power) if p is not None and p < -ON_THRESHOLD_W
        ]
        b.discharge_steps = [
            i for i, p in enumerate(power) if p is not None and p > ON_THRESHOLD_W
        ]
        b.charge_kwh = energy([-power[i] for i in b.charge_steps])
        b.discharge_kwh = energy([power[i] for i in b.discharge_steps])
        b.grid_charge_steps = [
            i
            for i in b.charge_steps
            if (pv[i] or 0.0) < -power[i] and (grid_pos[i] or 0.0) > ON_THRESHOLD_W
        ]
        socs = [s for s in soc if s is not None]
        if socs:
            b.soc_start, b.soc_end = socs[0], socs[-1]
            b.soc_min, b.soc_max = min(socs), max(socs)
            if b.soc_max > 1.5:
                b.notes.append("SOC column looks like percent, not a fraction")
        batteries.append(b)

    # ---- grid
    grid = GridSummary()
    grid.import_kwh = energy([g for g in grid_pos if g])
    grid.export_kwh = energy([-g for g in grid_neg if g])
    grid.peak_import_w = max((g for g in grid_pos if g), default=0.0)
    grid.pv_kwh = energy([p for p in pv if p])
    grid.load_kwh = energy([p for p in load if p])
    costs = _col(records, "cost_profit")
    if any(c is not None for c in costs):
        grid.cost_total = sum(c for c in costs if c is not None)

    horizon_hours = (n * dt_h) if dt_h else None
    return Summary(
        n_steps=n,
        step_minutes=step_minutes,
        optim_status=status,
        generated_at=plan.generated_at,
        schema_version=plan.schema_version,
        horizon_hours=horizon_hours,
        first_step=_fmt_time(stamps[0], tz) if stamps[0] else None,
        last_step=_fmt_time(stamps[-1], tz) if stamps[-1] else None,
        deferrables=deferrables,
        batteries=batteries,
        grid=grid,
        last_run=last_run,
        notes=notes,
        tz=str(tz) if tz else "UTC",
    )


def _list_at(config: dict, key: str, k: int):
    value = config.get(key)
    if isinstance(value, list) and k < len(value):
        return value[k]
    return None


def _apply_config_to_deferrable(
    d: DeferrableSummary, config: dict, n: int, step_minutes
) -> None:
    hours = _num(_list_at(config, "operating_hours_of_each_deferrable_load", d.index))
    if hours is not None and step_minutes:
        d.expected_steps = math.ceil(hours / (step_minutes / 60.0)) if hours > 0 else 0
    start = _num(_list_at(config, "start_timesteps_of_each_deferrable_load", d.index))
    end = _num(_list_at(config, "end_timesteps_of_each_deferrable_load", d.index))
    start_i = int(start) if start is not None else 0
    end_i = int(end) if end else n  # 0 means "until the end of the horizon"
    d.window_clamped = end_i > n or start_i < 0
    d.window = (max(0, start_i), min(end_i, n))
    if d.window_clamped:
        d.notes.append(
            f"configured window [{start_i}, {end_i}) exceeds the {n}-step horizon; "
            f"EMHASS clamps it to {d.window}"
        )
    if d.expected_steps is not None and d.expected_steps != d.on_steps:
        d.notes.append(
            f"planned {d.on_steps} steps but config asks for {d.expected_steps} "
            f"({hours:g} h at {step_minutes} min)"
            + (
                "; the load does not complete inside this horizon"
                if d.on_steps < d.expected_steps
                else ""
            )
        )
    lo, hi = d.window
    outside = [i for r in d.runs for i in range(r[0], r[1] + 1) if i < lo or i >= hi]
    if outside:
        d.notes.append(
            f"steps {outside} run outside the configured window [{lo}, {hi})"
        )


# ------------------------------------------------------------------------- rendering


def _kwh(v: float) -> str:
    return f"{v:.2f} kWh"


def _steps_to_hours(steps: list[int], step_minutes) -> str:
    if not steps:
        return "none"
    runs = _runs([i in set(steps) for i in range(max(steps) + 1)])
    parts = [f"{a}" if a == b else f"{a}-{b}" for a, b in runs]
    hours = f" ({len(steps) * step_minutes / 60:g} h)" if step_minutes else ""
    return "steps " + ", ".join(parts) + hours


def render(s: Summary) -> str:
    lines: list[str] = []
    if s.n_steps == 0:
        lines.append("STATUS: no-run - EMHASS has not produced a plan yet")
        lines.extend(f"  {n}" for n in s.notes)
        return "\n".join(lines)

    status = s.optim_status or "unknown"
    if status in OK_STATUSES:
        verdict = "plan is usable"
        if status == "Optimal (Relaxed)":
            verdict = (
                "usable, but the MILP was infeasible and EMHASS published a RELAXED solve: "
                "semi-continuous / single-constant load constraints were dropped, so loads may "
                "run at partial power or in several pieces"
            )
        elif status == "Optimal_Inaccurate":
            verdict = (
                "usable, solver hit its tolerance or time limit (Optimal_Inaccurate)"
            )
    else:
        verdict = (
            "NOT optimal - the plan below is empty or a fallback; fix the cause first"
        )
    lines.append(f"STATUS: {status} - {verdict}")

    horizon = f"{s.horizon_hours:g} h" if s.horizon_hours else "unknown length"
    step = f"{s.step_minutes} min" if s.step_minutes else "unknown"
    span = (
        f" from {s.first_step} to {s.last_step}" if s.first_step and s.last_step else ""
    )
    lines.append(
        f"Horizon: {s.n_steps} steps x {step} = {horizon}{span} (times in {s.tz})"
    )
    if s.generated_at:
        lines.append(
            f"Generated at: {s.generated_at} (schema {s.schema_version or '?'})"
        )
    if s.last_run:
        lr = s.last_run
        bits = [f"status={lr.get('status')}", f"action={lr.get('action')}"]
        if lr.get("duration_total_seconds") is not None:
            bits.append(f"duration={lr['duration_total_seconds']} s")
        if isinstance(lr.get("stage_times"), dict) and lr["stage_times"]:
            slow = max(lr["stage_times"].items(), key=lambda kv: kv[1] or 0)
            bits.append(f"slowest stage={slow[0]} ({slow[1]} s)")
        if lr.get("emhass_version"):
            bits.append(f"emhass={lr['emhass_version']}")
        lines.append("Last run: " + ", ".join(bits))
        if lr.get("error_message"):
            lines.append(f"  error_message: {lr['error_message']}")
    for note in s.notes:
        lines.append(f"Note: {note}")

    g = s.grid
    lines.append("")
    lines.append(
        f"Grid: import {_kwh(g.import_kwh)}, export {_kwh(g.export_kwh)}, "
        f"peak import {g.peak_import_w:.0f} W; PV {_kwh(g.pv_kwh)}, base load {_kwh(g.load_kwh)}"
        + (f"; cost_profit sum {g.cost_total:.3f}" if g.cost_total is not None else "")
    )

    for d in s.deferrables:
        lines.append("")
        lines.append(f"Deferrable load {d.index}:")
        if d.on_steps == 0:
            lines.append("  never runs in this horizon (0 steps on)")
        else:
            runs = ", ".join(f"{a}-{b}" if a != b else f"{a}" for a, b in d.runs)
            lines.append(
                f"  runs {d.on_steps} steps ({d.on_steps * s.step_minutes / 60:g} h) in "
                f"{len(d.runs)} block(s) [{runs}], {d.first_on} to {d.last_off}, "
                f"{_kwh(d.energy_kwh)} at up to {d.peak_w:.0f} W"
                if s.step_minutes
                else f"  runs {d.on_steps} steps in {len(d.runs)} block(s) [{runs}]"
            )
        if d.expected_steps is not None:
            lines.append(
                f"  config: {d.expected_steps} steps expected, window {d.window}"
            )
        if d.in_cheapest_window is not None and d.on_steps:
            if d.in_cheapest_window:
                lines.append(
                    f"  price: scheduled in the {d.on_steps} cheapest steps "
                    f"(avg {d.avg_price_on:.4f} vs horizon avg {d.avg_price_all:.4f})"
                )
            else:
                lines.append(
                    f"  price: NOT in the cheapest steps (avg on {d.avg_price_on:.4f} vs horizon avg "
                    f"{d.avg_price_all:.4f}); cheaper unused steps: {d.cheaper_unused_steps[:6]}. "
                    "Usual reasons: start/end window, min on/off time, max startups, PV "
                    "self-consumption or battery priority outweighing price, def_current_state."
                )
        for note in d.notes:
            lines.append(f"  note: {note}")

    for b in s.batteries:
        lines.append("")
        lines.append(f"Battery {b.index}:")
        if b.soc_start is not None:
            lines.append(
                f"  SOC {b.soc_start:.0%} -> {b.soc_end:.0%} (min {b.soc_min:.0%}, max {b.soc_max:.0%})"
            )
        lines.append(
            f"  charge {_kwh(b.charge_kwh)} in {_steps_to_hours(b.charge_steps, s.step_minutes)}"
        )
        lines.append(
            f"  discharge {_kwh(b.discharge_kwh)} in {_steps_to_hours(b.discharge_steps, s.step_minutes)}"
        )
        if b.grid_charge_steps:
            lines.append(
                f"  charges from the grid in {_steps_to_hours(b.grid_charge_steps, s.step_minutes)} "
                "(PV below charge power while importing)"
            )
        for note in b.notes:
            lines.append(f"  note: {note}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- driver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "plan", help="plan JSON file or http(s) URL of GET /api/v1/plan"
    )
    parser.add_argument(
        "--last-run", help="last_run JSON file or URL of GET /api/v1/last-run"
    )
    parser.add_argument(
        "--config", help="config.json used for the run (window / hours comparison)"
    )
    parser.add_argument(
        "--tz", help="IANA zone for displayed times, e.g. Europe/Berlin"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(argv)

    tz = None
    if args.tz:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            tz = ZoneInfo(args.tz)
        except (ZoneInfoNotFoundError, ValueError):
            print(f"ERROR: unknown time zone {args.tz}")
            return 2
    try:
        plan = load_plan(args.plan)
        last_run = load_json(args.last_run) if args.last_run else None
        config = load_json(args.config) if args.config else None
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: cannot read input: {exc}")
        return 2

    summary = analyze(plan, config=config, last_run=last_run, tz=tz)
    if args.json:
        print(json.dumps(asdict(summary), indent=2, default=str))
    else:
        print(render(summary))
    return 0 if summary.optim_status in OK_STATUSES else 1


if __name__ == "__main__":
    sys.exit(main())
