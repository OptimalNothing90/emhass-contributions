"""Consumable view over the adopted plan: per-demand setpoints, plan state, elapsed accounting."""

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from flexd.emhass_driver import PlanRejected

log = logging.getLogger(__name__)


class PlanStructureError(PlanRejected):
    """The plan does not match the payload flexd submitted (#1 Medium 9)."""


@dataclass(frozen=True)
class _Adopted:
    """One adoption: the plan, the mapping it was solved with and the instant it
    became effective. Immutable and swapped as one reference so a reader on the
    REST threadpool can never pair a new plan with the old mapping (#1 Lows)."""

    plan: dict
    mapping: dict
    adopted_at: datetime


@dataclass
class DemandView:
    setpoint_w: float
    on: bool
    clamped: bool
    truncated: bool = False
    unschedulable: bool = False
    # registry revision the slot was solved for (None for adopted files written
    # before it was mapped); live_demand_view compares the demand's revision to it
    revision: int | None = None


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _records_step(records: list[dict], default: timedelta) -> timedelta:
    if len(records) >= 2:
        return _parse(records[1]["timestamp"]) - _parse(records[0]["timestamp"])
    return default  # single-record plans: trust the configured grid, not a 30-min guess


def verify_plan_structure(plan: dict, mapping: dict, timestep: timedelta) -> None:
    """Fail loud before adoption instead of reading 0 on schema drift or rescaling
    every window on a flexd-vs-EMHASS timestep mismatch (#1 Medium 9).

    Every record is checked, not just the first two (Codex review 2026-10-17
    finding 4): upstream serialises NaN as null and a bad later timestamp used to
    pass, then float(None) failed at read or accrual time with the plan adopted.

    - every record is an object with an aware ISO timestamp;
    - consecutive timestamps are exactly one configured timestep apart;
    - every submitted slot 0..N-1 has a finite numeric P_deferrable{slot} in every
      record;
    - record 0 sits on the mapping's anchor, one step either way allowed (the
      rounding-boundary limit documented in aggregator.grid_anchor).
    """
    records = plan.get("plan")
    if not isinstance(records, list) or not records:
        raise PlanStructureError("plan carries no records for the submitted loads")
    keys = [f"P_deferrable{slot}" for slot in range(len(mapping))]
    previous: datetime | None = None
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise PlanStructureError(f"plan record {i} is not an object")
        try:
            ts = _parse(rec["timestamp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanStructureError(
                f"plan record {i} has no parseable timestamp: {exc!r}"
            ) from exc
        if ts.tzinfo is None:
            raise PlanStructureError(f"plan record {i} timestamp is not tz-aware")
        if previous is not None and ts - previous != timestep:
            raise PlanStructureError(
                f"plan step {ts - previous} between records {i - 1} and {i} differs "
                f"from the configured timestep {timestep}"
            )
        previous = ts
        for key in keys:
            if key not in rec:
                raise PlanStructureError(
                    f"plan record {i} lacks {key}; {len(mapping)} loads were submitted"
                )
            value = rec[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise PlanStructureError(
                    f"plan record {i} {key} is {value!r}, not a finite number"
                )
    anchors = {e.get("anchor") for e in mapping.values()} - {None}
    if anchors:
        anchor = _parse(anchors.pop())
        first = _parse(records[0]["timestamp"])
        if abs(first - anchor) > timestep:
            raise PlanStructureError(
                f"plan starts at {records[0]['timestamp']}, payload was anchored at "
                f"{anchor.isoformat()} (more than one step apart)"
            )


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
        # the ONLY mutable state: one reference, read once per call (snapshot)
        self._adopted: _Adopted | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._adopted = _Adopted(
                plan=raw["plan"],
                mapping=raw["mapping"],
                adopted_at=_parse(raw["adopted_at"]),
            )
        except Exception:
            log.warning(
                "adopted-plan file %s unreadable; starting as no-run", self._path
            )
            self._adopted = None  # corrupt view is recoverable: next cycle re-adopts

    def adopt(self, plan: dict, mapping: dict, now: datetime) -> None:
        # one reference swap: readers see either the previous adoption whole or this
        # one whole, never plan and mapping from different adoptions
        self._adopted = _Adopted(plan=plan, mapping=mapping, adopted_at=now)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"plan": plan, "mapping": mapping, "adopted_at": now.isoformat()}
                )
            )
            fh.flush()
            os.fsync(
                fh.fileno()
            )  # no .bak here: the tmp must be durable before the swap
        os.replace(tmp, self._path)  # atomic: a crash mid-write never corrupts the view

    def snapshot(self) -> tuple[dict | None, dict, datetime | None]:
        """(plan, mapping, adopted_at) from ONE adoption. Callers that need more than
        one of the three take this once instead of reading the properties one by one."""
        snap = self._adopted
        if snap is None:
            return None, {}, None
        return snap.plan, snap.mapping, snap.adopted_at

    def state(self, now: datetime) -> str:
        snap = self._adopted
        if snap is None:
            return "no-run"
        if now - snap.adopted_at > self._stale_after:
            return "stale"
        return "ok"

    @property
    def raw_plan(self) -> dict | None:
        snap = self._adopted
        return snap.plan if snap else None

    def mapped_ids(self) -> set[str]:
        snap = self._adopted
        return set(snap.mapping) if snap else set()

    @property
    def generated_at(self) -> str | None:
        snap = self._adopted
        return snap.plan.get("generated_at") if snap else None

    def _step(self, records: list[dict]) -> timedelta:
        return _records_step(records, self._timestep)

    def _record_at(self, records: list[dict], now: datetime) -> dict | None:
        current = None
        for rec in records:
            if _parse(rec["timestamp"]) <= now:
                current = rec
            else:
                break
        if current is None:
            # The plan is effective from adoption, not from its first timestamp: with
            # ts_round nearest EMHASS rounds the start up to half a step ahead, and
            # serving 0 until then would switch a running load off for up to half a
            # slot (e2e v0.18.6 observation 3). The first record covers up to one step
            # before its timestamp; a full step or more early is a real gap.
            if records and _parse(records[0]["timestamp"]) - now < self._step(records):
                return records[0]
            return None
        # a record only covers its own timestep; past plan end -> no coverage
        last_ts = _parse(records[-1]["timestamp"])
        if now >= last_ts + self._step(records):
            return None
        return current

    def demand_view(self, demand_id: str, now: datetime) -> DemandView | None:
        """View for one demand under the CURRENT adopted plan.

        Returns None when the demand is not part of the adopted plan's mapping
        (unknown id, or registered after the last solve). Callers must resolve
        registry membership separately: registered-but-unmapped means
        'pending next solve', not 'unknown'.
        """
        snap = self._adopted
        if snap is None or demand_id not in snap.mapping:
            return None
        entry = snap.mapping[demand_id]
        slot = entry["slot"]
        clamped = entry.get("clamped", False)
        rec = self._record_at(snap.plan["plan"], now)
        power = float(rec.get(f"P_deferrable{slot}", 0)) if rec else 0.0
        return DemandView(
            setpoint_w=power,
            on=power > 0,
            clamped=clamped,
            truncated=entry.get("truncated", False),
            unschedulable=entry.get("unschedulable", False),
            revision=entry.get("revision"),
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
        snap = self._adopted
        if snap is None or demand_id not in snap.mapping:
            return 0.0
        entry = snap.mapping[demand_id]
        slot = entry["slot"]
        # adopted files written before nominal_power_w was mapped: full-slot credit
        nominal = float(entry.get("nominal_power_w") or 0.0)
        records = snap.plan["plan"]
        step = self._step(records)
        total_h = 0.0
        for i, rec in enumerate(records):
            ts = _parse(rec["timestamp"])
            # the first record is also served up to one step early (_record_at); the
            # ledger credits what consumers were told, so its coverage starts there too,
            # but never before the plan was adopted (nothing was served before that)
            covered_from = max(ts - step, snap.adopted_at) if i == 0 else ts
            lo, hi = max(covered_from, since), min(ts + step, until)
            if hi <= lo:
                continue
            power = float(rec.get(f"P_deferrable{slot}", 0))
            if power <= 0:
                continue
            ratio = min(power / nominal, 1.0) if nominal > 0 else 1.0
            total_h += (hi - lo).total_seconds() / 3600 * ratio
        return total_h
