"""Single-writer demand registry with atomic JSON persistence."""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from flexd.models import Demand, utcnow

log = logging.getLogger(__name__)

# pending-clear bound: keep the newest across a long broker outage; the oldest were
# most likely cleared by publish_plan's mapped-but-inactive OFF anyway
MAX_PENDING_CLEAR = 1000
LEGACY_PENDING_CLEAR_FILE = "pending_clear.json"


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
    ):
        self._path = Path(path)
        self._bak = self._path.with_suffix(self._path.suffix + ".bak")
        self._demands: dict[str, Demand] = {}
        # ids whose retained MQTT topics still need clearing. Part of the snapshot:
        # delete and sweep write the removal and the clear job in ONE _save, so no
        # crash can leave a removed demand without its clear job (Codex review
        # 2026-10-17 finding 3). The scheduler drains it after a delivery succeeded.
        self._pending_clear: list[str] = []
        # next run identity to hand out (see Demand.revision); persisted with the
        # demands so a delete + restart never reissues a revision an adopted
        # mapping may still name
        self._next_revision = 1
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
        self._import_legacy_pending_clear()

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
            next_revision = raw.get("next_revision")
            pending = raw.get("pending_clear", [])
            if not isinstance(pending, list) or not all(
                isinstance(i, str) for i in pending
            ):
                log.warning(
                    "registry file %s: pending_clear is not a list of ids; dropped "
                    "(retained topics of ids deleted before may need a manual clear)",
                    candidate,
                )
                pending = []
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
            self._pending_clear = pending[-MAX_PENDING_CLEAR:]
            highest = max((d.revision for d in loaded.values()), default=0)
            if not isinstance(next_revision, int) or next_revision <= highest:
                # file written before the counter existed (or tampered): continue
                # above every revision still on record
                next_revision = highest + 1
            self._next_revision = next_revision
            return
        log.warning("no readable registry file, starting empty")
        self._demands = {}

    def _import_legacy_pending_clear(self) -> None:
        """Fold a pre-snapshot pending_clear.json (written next to the registry by
        earlier versions) into the snapshot once, then retire the file."""
        legacy = self._path.parent / LEGACY_PENDING_CLEAR_FILE
        if not legacy.exists():
            return
        try:
            ids = json.loads(legacy.read_text(encoding="utf-8"))
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                raise TypeError("pending-clear file must be a list of ids")
        except Exception:
            log.warning(
                "legacy pending-clear file %s unreadable; ignored (retained topics "
                "of ids deleted before may need a manual clear)",
                legacy,
            )
            return
        with self._lock:
            self._queue_clear(ids)
            self._save()
        legacy.unlink()  # the snapshot is durable at this point
        log.info("imported %d pending-clear ids from %s", len(ids), legacy)

    def _save(self) -> None:
        # order matters: write the new state to tmp FIRST; only after it exists on disk,
        # rotate the current file to .bak and swap tmp in. A crash at any point leaves
        # at least one readable file (tmp write fails -> path+bak untouched; crash between
        # replaces -> bak holds the previous state and _load falls back to it).
        payload = json.dumps(
            {
                "demands": [d.model_dump(mode="json") for d in self._demands.values()],
                "next_revision": self._next_revision,
                "pending_clear": self._pending_clear,
            },
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
    def upsert(self, demand: Demand, now: datetime | None = None) -> Demand:
        """Register or re-declare. `now` is injectable like refresh/list_active/sweep:
        expiry of the existing entry is judged against it, so pinned-time callers
        (materialize, templates) never see wall-clock expiry."""
        with self._lock:
            demand = demand.model_copy()
            now = now or utcnow()
            existing = self._demands.get(demand.id)
            if existing is not None and existing.expires_at <= now:
                # expired but not swept yet: gone as far as the API is concerned (same
                # rule as refresh). It owns nothing and is not the same run, so another
                # source may take the id now instead of after the next sweep (#1 Lows).
                existing = None
            if existing is not None and existing.source != demand.source:
                raise OwnershipError(
                    f"{demand.id} is owned by {existing.source!r}, not {demand.source!r}"
                )
            if existing is None:
                active = sum(1 for d in self._demands.values() if d.expires_at > now)
                if active >= self._max_demands:
                    raise RegistryFull(
                        f"registry holds {active} active demands; max_demands is "
                        f"{self._max_demands}"
                    )
            if existing is not None:
                # a re-declaration of a live demand (PUT, MQTT set) is the same run:
                # created_at and revision stay, so the adopted slot keeps serving it.
                # Only a delete (or expiry) followed by a new register starts a new
                # run (#1 Lows, Codex 2026-10-17 finding 2).
                demand.created_at = existing.created_at
                demand.revision = existing.revision
            else:
                demand.revision = self._next_revision
                self._next_revision += 1
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
            self._remove([demand_id])
            return removed

    def _remove(self, ids: list[str]) -> None:
        """Drop demands and queue their retained-topic clear in the same snapshot.
        Caller holds the lock."""
        for demand_id in ids:
            del self._demands[demand_id]
        self._queue_clear(ids)
        self._save()

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
            if expired:
                self._remove([d.id for d in expired])
            return expired

    # -- pending retained-topic clears ---------------------------------------
    def _queue_clear(self, ids) -> None:
        """Caller holds the lock and saves."""
        for demand_id in ids:
            if demand_id not in self._pending_clear:
                self._pending_clear.append(demand_id)
        if len(self._pending_clear) > MAX_PENDING_CLEAR:
            del self._pending_clear[:-MAX_PENDING_CLEAR]

    def pending_clear_ids(self) -> list[str]:
        with self._lock:
            return list(self._pending_clear)

    def queue_clear(self, ids) -> None:
        """Queue ids whose retained topics need clearing (delete and sweep do this
        themselves; this is for callers that learn of a stale id another way)."""
        with self._lock:
            before = list(self._pending_clear)
            self._queue_clear(ids)
            if self._pending_clear != before:
                self._save()

    def clear_delivered(self, ids) -> None:
        """Drop exactly these ids (the ones a delivery carried) and persist the drain;
        ids queued meanwhile stay for the next delivery."""
        gone = set(ids)
        with self._lock:
            kept = [i for i in self._pending_clear if i not in gone]
            if len(kept) != len(self._pending_clear):
                self._pending_clear = kept
                self._save()
