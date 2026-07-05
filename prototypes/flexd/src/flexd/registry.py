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
        for candidate in (self._path, self._bak):
            if not candidate.exists():
                continue
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                self._demands = {d["id"]: Demand(**d) for d in raw["demands"]}
                return
            except Exception:
                log.warning("registry file %s unreadable, trying fallback", candidate)
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

    def refresh(self, demand_id: str, source: str) -> Demand:
        with self._lock:
            d = self._check_owner(demand_id, source)
            d.expires_at = utcnow() + timedelta(seconds=d.ttl_s or 0)
            d.updated_at = utcnow()
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
