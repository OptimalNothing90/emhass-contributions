"""Single-writer demand registry with atomic JSON persistence."""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flexd.models import Demand, utcnow

log = logging.getLogger(__name__)


class OwnershipError(Exception):
    """Claimed source does not own this demand id."""


class DemandExpired(KeyError):
    """Refresh on a demand whose expires_at has passed: it is gone as far as the API is
    concerned, even if the sweep has not removed it yet. Register again instead."""


class Registry:
    """Single-writer demand registry with atomic JSON persistence.

    Returned Demand objects are defensive copies; mutating them never changes registry state.
    """

    def __init__(self, path: Path):
        self._path = Path(path)
        self._bak = self._path.with_suffix(self._path.suffix + ".bak")
        self._demands: dict[str, Demand] = {}
        self._deleted_ids: list[str] = []
        self._lock = threading.Lock()  # REST threadpool vs event-loop scheduler: _save is read-modify-write on shared files
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
        tmp.write_text(payload, encoding="utf-8")
        # no fsync before the renames: on power loss the bak fallback recovers the prior
        # state; accepted for the LAN MVP.
        if self._path.exists():
            os.replace(self._path, self._bak)
        os.replace(tmp, self._path)

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
            self._deleted_ids.append(demand_id)
            self._save()
            return removed

    def drain_deleted(self) -> list[str]:
        """Demand ids deleted since the last drain — the scheduler funnels these into
        retained-topic cleanup so no delete path can ghost MQTT topics."""
        with self._lock:
            drained, self._deleted_ids = self._deleted_ids, []
            return drained

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
            self._save()
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
