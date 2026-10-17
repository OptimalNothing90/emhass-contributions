"""Persisted queue of demand ids whose retained MQTT topics still need clearing.

A REST delete followed by a crash inside the debounce window used to leave
`plan/demands/{id}/on = 1` retained forever: the deleted and swept id queues were
memory-only (#1 Medium 11). This queue is written to the data dir with the same
tmp -> fsync -> replace discipline as the registry, reloaded on start and drained at
the first cycle end that delivers it.
"""

import json
import logging
import os
import threading
from collections.abc import Iterable
from pathlib import Path

log = logging.getLogger(__name__)

# keep the newest across a long broker outage; the oldest were most likely cleared by
# publish_plan's mapped-but-inactive OFF anyway
MAX_PENDING_IDS = 1000


class PendingClear:
    def __init__(self, path: Path | None = None, *, max_ids: int = MAX_PENDING_IDS):
        self._path = Path(path) if path is not None else None
        self._max = max_ids
        self._ids: list[str] = []
        # Registry.delete (REST threadpool) and the scheduler (event loop) both write
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, list) or not all(isinstance(i, str) for i in raw):
                raise TypeError("pending-clear file must be a list of ids")
        except Exception:
            log.warning(
                "pending-clear file %s unreadable; starting empty (retained topics of "
                "ids deleted before the crash may need a manual clear)",
                self._path,
            )
            return
        self._ids = raw[-self._max :]

    def _save(self) -> None:
        """Caller holds the lock. No .bak: a torn write loses at most the ids queued
        since the last cycle end, and the mapped ones are covered by publish_plan."""
        if self._path is None:
            return
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self._ids))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self._path)

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._ids)

    def add(self, ids: Iterable[str]) -> None:
        with self._lock:
            changed = False
            for demand_id in ids:
                if demand_id in self._ids:
                    continue
                self._ids.append(demand_id)
                changed = True
            if len(self._ids) > self._max:
                del self._ids[: -self._max]
                changed = True
            if changed:
                self._save()

    def remove(self, ids: Iterable[str]) -> None:
        """Drop exactly these ids (the ones a delivery carried); ids added meanwhile
        stay queued for the next delivery."""
        gone = set(ids)
        with self._lock:
            kept = [i for i in self._ids if i not in gone]
            if len(kept) != len(self._ids):
                self._ids = kept
                self._save()
