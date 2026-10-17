"""Single-writer demand registry with atomic JSON persistence."""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from flexd.models import Demand, utcnow
from flexd.pending_clear import PendingClear

log = logging.getLogger(__name__)


class OwnershipError(Exception):
    """Claimed source does not own this demand id."""


class DemandExpired(KeyError):
    """Refresh on a demand whose expires_at has passed: it is gone as far as the API is
    concerned, even if the sweep has not removed it yet. Register again instead."""


class RegistryFull(Exception):
    """Registering a NEW id would exceed max_demands (#1 Medium 12): the MILP and the
    registry file must not grow without limit on a buggy client."""


class Registry:
    """Single-writer demand registry with atomic JSON persistence.

    Returned Demand objects are defensive copies; mutating them never changes registry state.
    """

    def __init__(
        self,
        path: Path,
        *,
        max_demands: int = 32,
        save_debounce_s: float = 5.0,
        pending_clear: PendingClear | None = None,
    ):
        self._path = Path(path)
        self._bak = self._path.with_suffix(self._path.suffix + ".bak")
        self._demands: dict[str, Demand] = {}
        # ids whose retained MQTT topics still need clearing: every delete path queues
        # here, the scheduler delivers at cycle end. Persisted when given a path (#1
        # Medium 11); memory-only otherwise.
        self.pending_clear = pending_clear or PendingClear()
        self._lock = threading.Lock()  # REST threadpool vs event-loop scheduler: _save is read-modify-write on shared files
        self._max_demands = max_demands
        # Refresh bursts (a client re-arming every few seconds) must not rewrite the
        # whole file each time on an SD-card host (#1 Medium 12): a refresh inside the
        # debounce window only marks the state dirty and arms one timer that flushes it.
        # upsert, delete and sweep write immediately and take any pending refresh along.
        self._save_debounce_s = save_debounce_s
        self._dirty = False
        self._last_save = -float("inf")
        self._flush_timer: threading.Timer | None = None
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        """Load demands. The file must be JSON with a "demands" list; anything else falls
        back to .bak (structural damage). Inside a valid list, an invalid entry is logged
        and skipped so one bad record cannot empty the registry on restart (review 2, 5)."""
        for candidate in (self._path, self._bak):
            if not candidate.exists():
                continue
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                entries = raw["demands"]
                if not isinstance(raw, dict) or not isinstance(entries, list):
                    raise TypeError(
                        "registry file must be an object with a 'demands' list"
                    )
            except Exception:
                log.warning(
                    "registry file %s unreadable or malformed, trying fallback",
                    candidate,
                )
                continue
            loaded: dict[str, Demand] = {}
            for entry in entries:
                try:
                    d = Demand.model_validate(entry, context={"persisted": True})
                except Exception as exc:
                    log.error(
                        "registry entry %r in %s is invalid and was skipped: %s",
                        entry.get("id") if isinstance(entry, dict) else entry,
                        candidate,
                        exc,
                    )
                    continue
                loaded[d.id] = d
            self._demands = loaded
            return
        log.warning("no readable registry file, starting empty")
        self._demands = {}

    def _save(self) -> None:
        # order matters: write the new state to tmp FIRST; only after it exists on disk,
        # rotate the current file to .bak and swap tmp in. A crash at any point leaves
        # at least one readable file (tmp write fails -> path+bak untouched; crash between
        # replaces -> bak holds the previous state and _load falls back to it).
        payload = json.dumps(
            {"demands": [d.model_dump(mode="json") for d in self._demands.values()]},
            indent=2,
        )
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(
                fh.fileno()
            )  # the tmp content must be durable before it is renamed in
        if self._path.exists():
            os.replace(self._path, self._bak)
        os.replace(tmp, self._path)
        self._dirty = False
        self._last_save = time.monotonic()
        if self._flush_timer is not None:
            self._flush_timer.cancel()
            self._flush_timer = None

    def _save_deferred(self) -> None:
        """Write now if the debounce window has passed, else arm one flush timer.
        Caller holds the lock."""
        self._dirty = True
        if time.monotonic() - self._last_save >= self._save_debounce_s:
            self._save()
            return
        if self._flush_timer is None:
            self._flush_timer = threading.Timer(self._save_debounce_s, self.flush)
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def flush(self) -> None:
        """Write a pending deferred change now (timer callback, and at shutdown)."""
        with self._lock:
            if self._flush_timer is not None:
                self._flush_timer.cancel()
                self._flush_timer = None
            if self._dirty:
                self._save()

    # -- ownership guard ---------------------------------------------------
    def _check_owner(self, demand_id: str, source: str) -> Demand:
        existing = self._demands.get(demand_id)
        if existing is None:
            raise KeyError(demand_id)
        if existing.source != source:
            raise OwnershipError(
                f"{demand_id} is owned by {existing.source!r}, not {source!r}"
            )
        return existing

    # -- API ----------------------------------------------------------------
    def upsert(self, demand: Demand) -> Demand:
        with self._lock:
            demand = demand.model_copy()
            existing = self._demands.get(demand.id)
            if existing is not None and existing.source != demand.source:
                raise OwnershipError(
                    f"{demand.id} is owned by {existing.source!r}, not {demand.source!r}"
                )
            if existing is None:
                now = utcnow()
                active = sum(1 for d in self._demands.values() if d.expires_at > now)
                if active >= self._max_demands:
                    raise RegistryFull(
                        f"registry holds {active} active demands; max_demands is "
                        f"{self._max_demands}"
                    )
            if existing is not None:
                # a re-declaration of a live demand (PUT, MQTT set) is the same run:
                # created_at stays, so the adopted slot keeps serving it. Only a
                # delete followed by a new register moves created_at (#1 Lows).
                demand.created_at = existing.created_at
            demand.updated_at = utcnow()
            self._demands[demand.id] = demand
            self._save()
            return demand.model_copy()

    def get(self, demand_id: str) -> Demand | None:
        with self._lock:
            d = self._demands.get(demand_id)
            return d.model_copy() if d is not None else None

    def delete(self, demand_id: str, source: str) -> Demand:
        with self._lock:
            removed = self._check_owner(demand_id, source)
            del self._demands[demand_id]
            self._save()
            self.pending_clear.add([demand_id])
            return removed

    def refresh(
        self, demand_id: str, source: str, now: datetime | None = None
    ) -> Demand:
        """Keep a demand alive. Never shortens it (a template demand expires at
        deadline+ttl, and a flapping re-trigger must not pull expiry back to now+ttl
        and ahead of the deadline, #1 HIGH 2), never revives it: expiry is a business
        state, not a side effect of sweep timing (Codex review finding 5).
        `now` is injectable so expiry math is testable under pinned time."""
        with self._lock:
            now = now or utcnow()
            d = self._check_owner(demand_id, source)
            if d.expires_at <= now:
                raise DemandExpired(demand_id)
            d.expires_at = max(d.expires_at, now + timedelta(seconds=d.ttl_s or 0))
            d.updated_at = now
            self._save_deferred()  # expires_at/updated_at only: coalesce bursts
            return d.model_copy()

    def list_active(self, now: datetime | None = None) -> list[Demand]:
        with self._lock:
            now = now or utcnow()
            return sorted(
                (d.model_copy() for d in self._demands.values() if d.expires_at > now),
                key=lambda d: d.id,
            )

    def sweep(self, now: datetime | None = None) -> list[Demand]:
        with self._lock:
            now = now or utcnow()
            expired = [d for d in self._demands.values() if d.expires_at <= now]
            for d in expired:
                del self._demands[d.id]
            if expired:
                self._save()
            return expired
