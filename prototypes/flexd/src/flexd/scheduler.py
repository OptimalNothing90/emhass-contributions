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
        self._debounce_sleeping = False
        self.last_result: str = "no-run"
        self._cycle_lock = asyncio.Lock()
        self._pending_swept: list[str] = []
        # Event loop captured for threadsafe notify_change: FastAPI runs sync `def`
        # handlers in a worker thread, where asyncio.get_event_loop() would fail.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def run_once(self, now: datetime | None = None) -> str:
        now = now or utcnow()
        # one cycle at a time: tick, debounce and POST /cycle would otherwise interleave
        # at the driver await and adopt a plan with the WRONG mapping (solve results are
        # read back from a shared endpoint)
        async with self._cycle_lock:
            swept = self._registry.sweep(now=now)
            self._pending_swept.extend(d.id for d in swept)
            # ORDER MATTERS: materialize accrues the OLD plan's on-hours into the standing
            # ledger, so it must run before this cycle's adopt() replaces the plan.
            self._standing.materialize(
                now=now, elapsed_lookup=self._view.on_hours_elapsed
            )
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
            self._write_crumb(now, payload if demands else None, result)
            self.last_result = result
            if self._on_cycle_end is not None:
                to_deliver = list(self._pending_swept)
                try:
                    await self._on_cycle_end(result, to_deliver)
                    self._pending_swept.clear()
                except Exception:
                    log.exception("on_cycle_end failed; swept ids kept for redelivery")
            return result

    def _write_crumb(self, now: datetime, payload: dict | None, result: str) -> None:
        if self._crumb_path is None:
            return
        try:
            crumb = {
                "at": now.isoformat(),
                "payload_sha256": None
                if payload is None
                else hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "result": result,
            }
            self._crumb_path.write_text(
                json.dumps(crumb, indent=2, default=str), encoding="utf-8"
            )
        except Exception:
            log.warning("crumb write failed", exc_info=True)

    def notify_change(self) -> None:
        """Debounced re-solve after a demand mutation. Threadsafe: callable from
        FastAPI sync handlers running in a worker thread."""

        def _schedule() -> None:
            # cancel only while sleeping: a debounce already solving must finish (lock serializes anyway)
            if (
                self._debounce_task is not None
                and not self._debounce_task.done()
                and self._debounce_sleeping
            ):
                self._debounce_task.cancel()
            # mark sleeping at schedule time: the coroutine only runs after the caller
            # yields, so a back-to-back notify would otherwise miss the cancel window
            self._debounce_sleeping = True
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
            self._debounce_sleeping = True
            await asyncio.sleep(self.debounce_s)
            self._debounce_sleeping = False
            await self.run_once()
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("debounced cycle failed")

    async def run_forever(self) -> None:
        self.bind_loop(asyncio.get_running_loop())
        interval = self._timestep_min * 60
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("cycle crashed; continuing")
            # sleep AFTER work: cadence drifts by solve duration — accepted for MVP
            # (payload is rebuilt from now each cycle)
            await asyncio.sleep(interval)
