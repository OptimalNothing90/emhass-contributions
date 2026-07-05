"""Cycle loop: sweep -> materialize standing -> aggregate -> solve -> adopt.

Also writes last_cycle.json debug crumb and exposes a debounced change trigger.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from flexd.aggregator import build_runtimeparams
from flexd.emhass_driver import PlanRejected
from flexd.models import utcnow

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        *,
        registry,
        driver,
        view,
        standing,
        timestep_min: int,
        horizon_steps: int,
        extra_runtime_params: dict,
        crumb_path: Path | None = None,
        on_cycle_end=None,
    ):
        self._registry = registry
        self._driver = driver
        self._view = view
        self._standing = standing
        self._timestep_min = timestep_min
        self._horizon = horizon_steps
        self._extra = extra_runtime_params
        self._crumb_path = crumb_path
        self._on_cycle_end = (
            on_cycle_end  # async callback(state, swept_ids) for mqtt publish
        )
        self.debounce_s = 10.0
        self._debounce_task: asyncio.Task | None = None
        self.last_result: str = "no-run"
        # Event loop captured for threadsafe notify_change: FastAPI runs sync `def`
        # handlers in a worker thread, where asyncio.get_event_loop() would fail.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def run_once(self, now: datetime | None = None) -> str:
        now = now or utcnow()
        swept = self._registry.sweep(now=now)
        # ORDER MATTERS: materialize accrues the OLD plan's on-hours into the standing
        # ledger, so it must run before this cycle's adopt() replaces the plan.
        self._standing.materialize(now=now, elapsed_lookup=self._view.on_hours_elapsed)
        demands = self._registry.list_active(now=now)
        if not demands:
            result = "skipped"
        else:
            payload, mapping = build_runtimeparams(
                demands,
                now=now,
                extra=self._extra,
                timestep_min=self._timestep_min,
                horizon_steps=self._horizon,
            )
            try:
                plan = await self._driver.run_cycle(
                    payload, last_generated_at=self._view.generated_at
                )
                self._view.adopt(plan, mapping, now=now)
                result = "ok"
            except PlanRejected as exc:
                log.error("plan rejected: %s", exc)
                result = "rejected"
            except httpx.HTTPError as exc:
                log.error("emhass unreachable: %s", exc)
                result = "down"
            self._write_crumb(now, payload, result)
        self.last_result = result
        if self._on_cycle_end is not None:
            await self._on_cycle_end(result, [d.id for d in swept])
        return result

    def _write_crumb(self, now: datetime, payload: dict, result: str) -> None:
        if self._crumb_path is None:
            return
        crumb = {
            "at": now.isoformat(),
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
            "result": result,
        }
        self._crumb_path.write_text(json.dumps(crumb, indent=2), encoding="utf-8")

    def notify_change(self) -> None:
        """Debounced re-solve after a demand mutation. Threadsafe: callable from
        FastAPI sync handlers running in a worker thread."""

        def _schedule() -> None:
            if self._debounce_task is not None and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._debounce_task = asyncio.ensure_future(self._debounced())

        try:
            asyncio.get_running_loop()  # already on the loop (async handler / tests)
            _schedule()
        except RuntimeError:
            if self._loop is None:
                log.warning(
                    "notify_change before loop bound; next tick will pick it up"
                )
                return
            self._loop.call_soon_threadsafe(_schedule)

    async def _debounced(self) -> None:
        try:
            await asyncio.sleep(self.debounce_s)
            await self.run_once()
        except asyncio.CancelledError:
            pass

    async def run_forever(self) -> None:
        self.bind_loop(asyncio.get_running_loop())
        interval = self._timestep_min * 60
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("cycle crashed; continuing")
            await asyncio.sleep(interval)
