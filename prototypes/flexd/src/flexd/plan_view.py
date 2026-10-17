"""Consumable view over the adopted plan: per-demand setpoints, plan state, elapsed accounting."""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from flexd.emhass_driver import PlanRejected

log = logging.getLogger(__name__)


class PlanStructureError(PlanRejected):
    """The plan does not match the payload flexd submitted (#1 Medium 9)."""


@dataclass
class DemandView:
    setpoint_w: float
    on: bool
    clamped: bool
    truncated: bool = False
    unschedulable: bool = False


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _records_step(records: list[dict], default: timedelta) -> timedelta:
    if len(records) >= 2:
        return _parse(records[1]["timestamp"]) - _parse(records[0]["timestamp"])
    return default  # single-record plans: trust the configured grid, not a 30-min guess


def verify_plan_structure(plan: dict, mapping: dict, timestep: timedelta) -> None:
    """Fail loud before adoption instead of reading 0 on schema drift or rescaling
    every window on a flexd-vs-EMHASS timestep mismatch (#1 Medium 9).

    - every submitted slot 0..N-1 has a P_deferrable{slot} column in every record;
    - the plan's record step equals the configured timestep;
    - record 0 sits on the mapping's anchor, one step either way allowed (the
      rounding-boundary limit documented in aggregator.grid_anchor).
    """
    records = plan.get("plan")
    if not isinstance(records, list) or not records:
        raise PlanStructureError("plan carries no records for the submitted loads")
    try:
        for slot in range(len(mapping)):
            key = f"P_deferrable{slot}"
            for i, rec in enumerate(records):
                if key not in rec:
                    raise PlanStructureError(
                        f"plan record {i} lacks {key}; {len(mapping)} loads were submitted"
                    )
        step = _records_step(records, timestep)
        if step != timestep:
            raise PlanStructureError(
                f"plan step {step} differs from the configured timestep {timestep}"
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
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanStructureError(f"plan records are malformed: {exc!r}") from exc


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
        return _records_step(self._records(), self._timestep)

    def _record_at(self, now: datetime) -> dict | None:
        current = None
        records = self._records()
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
            if records and _parse(records[0]["timestamp"]) - now < self._step():
                return records[0]
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
        for i, rec in enumerate(self._records()):
            ts = _parse(rec["timestamp"])
            # the first record is also served up to one step early (_record_at); the
            # ledger credits what consumers were told, so its coverage starts there too,
            # but never before the plan was adopted (nothing was served before that)
            covered_from = max(ts - step, self._adopted_at) if i == 0 else ts
            lo, hi = max(covered_from, since), min(ts + step, until)
            if hi <= lo:
                continue
            power = float(rec.get(f"P_deferrable{slot}", 0))
            if power <= 0:
                continue
            ratio = min(power / nominal, 1.0) if nominal > 0 else 1.0
            total_h += (hi - lo).total_seconds() / 3600 * ratio
        return total_h
