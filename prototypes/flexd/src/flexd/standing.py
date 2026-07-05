"""Standing demands: config definitions materialized into ordinary registry demands.

Day-state (elapsed accrual, corrections, done) lives in a ledger keyed (id, local_date).
"""

import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flexd.config import StandingDefinition
from flexd.models import Demand
from flexd.registry import Registry

CONFIG_SOURCE = "config"


class StandingManager:
    def __init__(
        self,
        definitions: list[StandingDefinition],
        *,
        ledger_path: Path,
        tz: str,
        registry: Registry,
    ):
        self._defs = {d.id: d for d in definitions}
        self._ledger_path = Path(ledger_path)
        self._tz = ZoneInfo(tz)
        self._registry = registry
        self._ledger: dict = self._load_ledger()

    def _load_ledger(self) -> dict:
        if self._ledger_path.exists():
            try:
                return json.loads(self._ledger_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_ledger(self) -> None:
        tmp = self._ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._ledger, indent=2), encoding="utf-8")
        os.replace(tmp, self._ledger_path)  # atomic, same principle as the registry

    def _day_key(self, demand_id: str, now: datetime) -> str:
        local_date = now.astimezone(self._tz).date().isoformat()
        return f"{demand_id}:{local_date}"

    def _entry(self, demand_id: str, now: datetime) -> dict:
        return self._ledger.setdefault(
            self._day_key(demand_id, now),
            {
                "done": False,
                "day_target_override_h": None,
                "elapsed_h": 0.0,  # cumulative across adoptions (rolling MPC never carries the day)
                "last_accrual": None,  # ISO instant of the last accrual upper bound
            },
        )

    def _window_utc(
        self, defn: StandingDefinition, now: datetime
    ) -> tuple[datetime, datetime]:
        local = now.astimezone(self._tz)
        start_h, start_m = map(int, defn.window[0].split(":"))
        end_h, end_m = map(int, defn.window[1].split(":"))
        start = datetime.combine(local.date(), time(start_h, start_m), tzinfo=self._tz)
        end = datetime.combine(local.date(), time(end_h, end_m), tzinfo=self._tz)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    # -- API ------------------------------------------------------------------
    def materialize(self, now: datetime, elapsed_lookup) -> None:
        """elapsed_lookup(id, since_utc, until_utc) -> on-hours in the CURRENT adopted plan.

        MUST run before this cycle's plan is adopted: it accrues the OLD plan's
        on-hours into the ledger (rolling MPC plans start at 'now', so the
        current plan alone never carries the whole day).
        """
        for defn in self._defs.values():
            win_start, win_end = self._window_utc(defn, now)
            entry = self._entry(defn.id, now)
            # accrue old-plan on-hours since the last accrual, clamped to the window
            accrual_start = win_start
            if entry["last_accrual"] is not None:
                accrual_start = max(
                    datetime.fromisoformat(entry["last_accrual"]), win_start
                )
            accrual_end = min(now, win_end)
            if accrual_end > accrual_start:
                entry["elapsed_h"] += elapsed_lookup(
                    defn.id, accrual_start, accrual_end
                )
                entry["last_accrual"] = accrual_end.isoformat()
            if entry["done"] or not (win_start <= now < win_end):
                continue
            override = entry["day_target_override_h"]
            # explicit None-check: correct(remaining=0.0) legitimately writes override 0.0
            target_h = override if override is not None else defn.effective_daily_hours
            remaining_h = target_h - entry["elapsed_h"]
            if remaining_h <= 0:
                # a previously-materialized instance must not keep soliciting energy
                if self._registry.get(defn.id) is not None:
                    self._registry.delete(defn.id, source=CONFIG_SOURCE)
                continue
            self._registry.upsert(
                Demand(
                    id=defn.id,
                    source=CONFIG_SOURCE,
                    type=defn.type,
                    nominal_power_w=defn.nominal_power_w,
                    energy_target_wh=remaining_h * defn.nominal_power_w,
                    window_start=win_start if win_start > now else None,
                    deadline=win_end,
                    expires_at=win_end,
                    interruptible=defn.interruptible,
                )
            )
        self._save_ledger()

    def correct(self, demand_id: str, *, remaining_hours: float, now: datetime) -> None:
        """Rebase today's target: override = remaining + elapsed_h (ledger), so the
        normal `target − elapsed` formula keeps working and survives restarts."""
        entry = self._entry(demand_id, now)
        entry["day_target_override_h"] = remaining_hours + entry["elapsed_h"]
        self._save_ledger()

    def mark_done(self, demand_id: str, now: datetime) -> None:
        entry = self._entry(demand_id, now)
        entry["done"] = True
        if self._registry.get(demand_id) is not None:
            self._registry.delete(demand_id, source=CONFIG_SOURCE)
        self._save_ledger()

    def is_standing(self, demand_id: str) -> bool:
        return demand_id in self._defs
