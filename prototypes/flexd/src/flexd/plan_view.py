"""Consumable view over the adopted plan: per-demand setpoints, plan state, elapsed accounting."""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DemandView:
    setpoint_w: float
    on: bool
    clamped: bool
    truncated: bool = False
    unschedulable: bool = False


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class PlanView:
    def __init__(
        self,
        path: Path,
        stale_after: timedelta,
        timestep: timedelta = timedelta(minutes=30),
    ):
        self._path = Path(path)
        self._stale_after = stale_after
        self._timestep = timestep
        self._plan: dict | None = None
        self._mapping: dict = {}
        self._adopted_at: datetime | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._plan = raw["plan"]
            self._mapping = raw["mapping"]
            self._adopted_at = _parse(raw["adopted_at"])
        except Exception:
            log.warning(
                "adopted-plan file %s unreadable; starting as no-run", self._path
            )
            self._plan = None  # corrupt view is recoverable: next cycle re-adopts

    def adopt(self, plan: dict, mapping: dict, now: datetime) -> None:
        self._plan, self._mapping, self._adopted_at = plan, mapping, now
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"plan": plan, "mapping": mapping, "adopted_at": now.isoformat()}
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)  # atomic: a crash mid-write never corrupts the view

    def state(self, now: datetime) -> str:
        if self._plan is None:
            return "no-run"
        if now - self._adopted_at > self._stale_after:
            return "stale"
        return "ok"

    @property
    def raw_plan(self) -> dict | None:
        return self._plan

    def mapped_ids(self) -> set[str]:
        return set(self._mapping)

    @property
    def generated_at(self) -> str | None:
        return self._plan.get("generated_at") if self._plan else None

    def _records(self) -> list[dict]:
        return self._plan["plan"] if self._plan else []

    def _step(self) -> timedelta:
        records = self._records()
        if len(records) >= 2:
            return _parse(records[1]["timestamp"]) - _parse(records[0]["timestamp"])
        return (
            self._timestep
        )  # single-record plans: trust the configured grid, not a 30-min guess

    def _record_at(self, now: datetime) -> dict | None:
        current = None
        for rec in self._records():
            if _parse(rec["timestamp"]) <= now:
                current = rec
            else:
                break
        if current is None:
            return None
        # a record only covers its own timestep; past plan end -> no coverage
        records = self._records()
        last_ts = _parse(records[-1]["timestamp"])
        if now >= last_ts + self._step():
            return None
        return current

    def demand_view(self, demand_id: str, now: datetime) -> DemandView | None:
        """View for one demand under the CURRENT adopted plan.

        Returns None when the demand is not part of the adopted plan's mapping
        (unknown id, or registered after the last solve). Callers must resolve
        registry membership separately: registered-but-unmapped means
        'pending next solve', not 'unknown'.
        """
        if self._plan is None or demand_id not in self._mapping:
            return None
        entry = self._mapping[demand_id]
        slot = entry["slot"]
        clamped = entry.get("clamped", False)
        rec = self._record_at(now)
        power = float(rec.get(f"P_deferrable{slot}", 0)) if rec else 0.0
        return DemandView(
            setpoint_w=power,
            on=power > 0,
            clamped=clamped,
            truncated=entry.get("truncated", False),
            unschedulable=entry.get("unschedulable", False),
        )

    def on_hours_elapsed(
        self, demand_id: str, since: datetime, until: datetime
    ) -> float:
        """Nominal-equivalent on-hours from the CURRENT adopted plan over [since, until).

        Each plan record covers [timestamp, timestamp+step). The credited time is the
        overlap of that interval with [since, until), scaled by P/nominal (capped at 1).
        Bounds are live wall-clock instants that never sit on the grid, so partial
        slots must count (#1 HIGH 1); the ratio keeps the accounting right under
        continuous deferrables too (#1 Medium 6). Adjacent calls partition exactly.

        Cross-adoption accumulation is the standing ledger's job (the scheduler
        accrues before each adoption).
        """
        if self._plan is None or demand_id not in self._mapping:
            return 0.0
        entry = self._mapping[demand_id]
        slot = entry["slot"]
        # adopted files written before nominal_power_w was mapped: full-slot credit
        nominal = float(entry.get("nominal_power_w") or 0.0)
        step = self._step()
        total_h = 0.0
        for rec in self._records():
            ts = _parse(rec["timestamp"])
            lo, hi = max(ts, since), min(ts + step, until)
            if hi <= lo:
                continue
            power = float(rec.get(f"P_deferrable{slot}", 0))
            if power <= 0:
                continue
            ratio = min(power / nominal, 1.0) if nominal > 0 else 1.0
            total_h += (hi - lo).total_seconds() / 3600 * ratio
        return total_h
