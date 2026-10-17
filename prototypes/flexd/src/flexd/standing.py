"""Standing demands: config definitions materialized into ordinary registry demands.

Day-state (elapsed accrual, corrections, done) lives in a ledger keyed (id, local_date).
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flexd.config import StandingDefinition
from flexd.models import Demand
from flexd.registry import OwnershipError, Registry, RegistryFull

log = logging.getLogger(__name__)

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
        self._bak = self._ledger_path.with_suffix(self._ledger_path.suffix + ".bak")
        self._tz = ZoneInfo(tz)
        self._registry = registry
        # REST threadpool (correct, mark_done) vs event-loop scheduler (materialize,
        # accrue): every public method is a read-modify-write on the ledger and its file
        # (#1 Medium 2). Same discipline as Registry; lock order is standing -> registry,
        # never the reverse.
        self._lock = threading.Lock()
        self._ledger: dict = self._load_ledger()

    def _load_ledger(self) -> dict:
        """Ledger, else its .bak, else empty. A torn ledger would otherwise silently zero
        the day's elapsed hours (over-delivery that day)."""
        for candidate in (self._ledger_path, self._bak):
            if not candidate.exists():
                continue
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise TypeError("ledger must be a JSON object")
                return raw
            except Exception:
                log.warning(
                    "standing ledger %s unreadable or malformed, trying fallback",
                    candidate,
                )
        log.warning("no readable standing ledger, starting with an empty day")
        return {}

    def _save_ledger(self) -> None:
        # tmp first, then rotate the current file to .bak, then swap tmp in: a crash at
        # any point leaves at least one readable file (see Registry._save). The tmp name
        # is unique per call so two writers can never share (and tear) one file.
        fd, tmp_name = tempfile.mkstemp(
            dir=self._ledger_path.parent, prefix=self._ledger_path.name, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(self._ledger, indent=2))
                fh.flush()
                os.fsync(fh.fileno())
        except Exception:
            os.unlink(tmp_name)
            raise
        if self._ledger_path.exists():
            os.replace(self._ledger_path, self._bak)
        os.replace(tmp_name, self._ledger_path)

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
    def _accrue_one(
        self, defn: StandingDefinition, now: datetime, elapsed_lookup
    ) -> tuple[dict, datetime, datetime]:
        """Credit old-plan on-hours since the last accrual, clamped to the window."""
        win_start, win_end = self._window_utc(defn, now)
        entry = self._entry(defn.id, now)
        accrual_start = win_start
        if entry["last_accrual"] is not None:
            last = datetime.fromisoformat(entry["last_accrual"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            accrual_start = max(last, win_start)
        accrual_end = min(now, win_end)
        if accrual_end > accrual_start:
            entry["elapsed_h"] += elapsed_lookup(defn.id, accrual_start, accrual_end)
            entry["last_accrual"] = accrual_end.isoformat()
        return entry, win_start, win_end

    def _prune_ledger(self, now: datetime) -> None:
        # day-keyed: past days are dead weight; prune so the file can't grow unbounded
        today = now.astimezone(self._tz).date().isoformat()
        self._ledger = {k: v for k, v in self._ledger.items() if k.endswith(today)}

    def accrue(self, now: datetime, elapsed_lookup) -> None:
        """Credit the CURRENT adopted plan's on-hours up to `now` into the ledger.
        Called by the scheduler right before a new plan is adopted, with the real
        adoption instant, so the old plan is accounted until it actually stops being
        served (Codex review 2026-10-16 finding 4). Never touches the registry."""
        with self._lock:
            self._prune_ledger(now)
            for defn in self._defs.values():
                self._accrue_one(defn, now, elapsed_lookup)
            self._save_ledger()

    def materialize(self, now: datetime, elapsed_lookup) -> None:
        """elapsed_lookup(id, since_utc, until_utc) -> nominal-equivalent on-hours in the
        CURRENT adopted plan over [since, until). Bounds are live instants (never
        grid-aligned); the lookup credits partial slots so consecutive cycles
        partition the day exactly.

        Accrues up to `now`, then (re)registers each standing definition inside its
        window with the remaining energy. Runs at cycle start, before this cycle's
        plan is adopted; the demands it writes feed this cycle's payload. Plan
        energy is an estimate of delivery until a consumption feedback exists.

        After downtime across local midnight, yesterday's un-accrued tail is
        deliberately dropped: yesterday's ledger entry and instance are both
        dead; today accrues from today's window start.
        """
        with self._lock:
            self._prune_ledger(now)
            for defn in self._defs.values():
                try:
                    entry, win_start, win_end = self._accrue_one(
                        defn, now, elapsed_lookup
                    )
                    if entry["done"] or not (win_start <= now < win_end):
                        continue
                    override = entry["day_target_override_h"]
                    # explicit None-check: correct(remaining=0.0) legitimately writes override 0.0
                    target_h = (
                        override if override is not None else defn.effective_daily_hours
                    )
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
                            window_start=None,  # materialize only runs inside the window (guard above); pre-window seeding is future work
                            deadline=win_end,
                            expires_at=win_end,
                            interruptible=defn.interruptible,
                            modulating=defn.modulating,
                        )
                    )
                except (OwnershipError, RegistryFull) as exc:
                    log.warning("standing %s skipped this cycle: %s", defn.id, exc)
                    continue
            self._save_ledger()

    def correct(
        self,
        demand_id: str,
        *,
        now: datetime,
        remaining_wh: float | None = None,
        nominal_power_w: float | None = None,
        remaining_hours: float | None = None,
    ) -> float:
        """Rebase today's target: override = remaining + elapsed_h (ledger), so the
        normal `target − elapsed` formula keeps working and survives restarts.

        Clients correct in energy (`remaining_wh`); the hours are taken at the
        DEFINITION's power, which is the power the remaining energy is materialized
        at again. Converting at the client's `nominal_power_w` and back at the
        definition's mis-scaled the correction whenever the two differed (#1 Lows);
        a difference above 1 % is logged, because the client's idea of the device is
        off. `remaining_hours` is accepted directly (already at definition power).
        Returns the remaining hours at definition power."""
        defn = self._defs.get(demand_id)
        if defn is None:
            raise KeyError(demand_id)
        if remaining_hours is None:
            if remaining_wh is None:
                raise ValueError("correct needs remaining_wh or remaining_hours")
            remaining_hours = remaining_wh / defn.nominal_power_w
            if (
                nominal_power_w is not None
                and abs(nominal_power_w - defn.nominal_power_w) / defn.nominal_power_w
                > 0.01
            ):
                log.warning(
                    "standing %s: correction sent with nominal_power_w %s, definition "
                    "has %s; %s Wh is %.3f h at the definition's power",
                    demand_id,
                    nominal_power_w,
                    defn.nominal_power_w,
                    remaining_wh,
                    remaining_hours,
                )
        with self._lock:
            entry = self._entry(demand_id, now)
            entry["day_target_override_h"] = remaining_hours + entry["elapsed_h"]
            self._save_ledger()
        return remaining_hours

    def mark_done(self, demand_id: str, now: datetime) -> None:
        if demand_id not in self._defs:
            raise KeyError(demand_id)
        with self._lock:
            entry = self._entry(demand_id, now)
            entry["done"] = True
            if self._registry.get(demand_id) is not None:
                self._registry.delete(demand_id, source=CONFIG_SOURCE)
            self._save_ledger()

    def is_standing(self, demand_id: str) -> bool:
        return demand_id in self._defs
