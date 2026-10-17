"""Cycle loop: sweep -> materialize standing -> aggregate -> solve -> adopt.

Also writes last_cycle.json debug crumb and exposes a debounced change trigger.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from flexd.aggregator import build_runtimeparams, grid_anchor
from flexd.emhass_driver import PlanRejected
from flexd.models import utcnow
from flexd.pending_clear import PendingClear
from flexd.plan_view import verify_plan_structure

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
        on_demand_off=None,
        clock=None,
        ts_round: str = "nearest",
        cycle_offset_s: float = 5.0,
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
        self._on_demand_off = (
            on_demand_off  # async callback(demand_id) -> publish OFF now
        )
        # injectable wall clock: the plan adoption instant is read here
        self._clock = clock or utcnow
        self._clock_injected = clock is not None
        self._ts_round = ts_round  # grid anchor rule, must equal EMHASS method_ts_round
        # run_forever fires this many seconds after each grid boundary
        self.cycle_offset_s = float(cycle_offset_s)
        self.debounce_s = 10.0
        self._debounce_task: asyncio.Task | None = None
        self._debounce_sleeping = False
        self.last_result: str = "no-run"
        self._cycle_lock = asyncio.Lock()
        # ids awaiting retained-topic cleanup: shared with the registry (every delete
        # path queues there) and persisted across a crash when the registry was given
        # a path (#1 Medium 11)
        self._pending: PendingClear = (
            getattr(registry, "pending_clear", None) or PendingClear()
        )
        # Event loop captured for threadsafe notify_change: FastAPI runs sync `def`
        # handlers in a worker thread, where asyncio.get_event_loop() would fail.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def run_once(self, now: datetime | None = None) -> str:
        # one cycle at a time: tick, debounce and POST /cycle would otherwise interleave
        # at the driver await and adopt a plan with the WRONG mapping (solve results are
        # read back from a shared endpoint)
        async with self._cycle_lock:
            pinned = now is not None
            now = now or self._clock()
            swept = self._registry.sweep(now=now)
            if self._on_cycle_end is not None:
                self._pending.add([d.id for d in swept])
            else:
                # nothing to deliver to: drain so the queue is never perpetual
                self._pending.remove(self._pending.ids())
            # ORDER MATTERS: materialize accrues the OLD plan's on-hours into the standing
            # ledger up to cycle start; the tail until the real switch is accrued below.
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
                    ts_round=self._ts_round,
                )
                try:
                    plan = await self._driver.run_cycle(
                        payload,
                        last_generated_at=self._view.generated_at,
                        now=now,
                        timestep_min=self._timestep_min,
                    )
                    # structural match against what was submitted, before anything is
                    # credited or adopted (raises PlanRejected)
                    verify_plan_structure(
                        plan, mapping, timedelta(minutes=self._timestep_min)
                    )
                    # The old plan was served until this instant; credit it up to here,
                    # then make the new plan effective from here (Codex review finding 4).
                    # The cycle's `now` stays the payload anchor; the switch instant is the
                    # real clock when running live (or when a test injects one); a pinned
                    # `now` without an injected clock stays pinned so deterministic tests
                    # never see wall-clock dates (plan review finding 6).
                    if self._clock_injected or not pinned:
                        switch_at = max(now, self._clock())
                    else:
                        switch_at = now
                    self._standing.accrue(
                        now=switch_at, elapsed_lookup=self._view.on_hours_elapsed
                    )
                    self._view.adopt(plan, mapping, now=switch_at)
                    result = "ok"
                except PlanRejected as exc:
                    log.error("plan rejected: %s", exc)
                    result = "rejected"
                except httpx.HTTPStatusError as exc:
                    if 400 <= exc.response.status_code < 500:
                        # EMHASS answered and refused the payload or its own configuration
                        # (e2e v0.18.6 observation 2): that is a rejection, not an outage.
                        # The body is EMHASS's log tail and says why; keep it bounded.
                        log.error(
                            "emhass rejected the optim request (HTTP %d): %s",
                            exc.response.status_code,
                            exc.response.text[:500],
                        )
                        result = "rejected"
                    else:
                        log.error("emhass unreachable: %s", exc)
                        result = "down"
                except httpx.HTTPError as exc:
                    log.error("emhass unreachable: %s", exc)
                    result = "down"
            self._write_crumb(now, payload if demands else None, result)
            self.last_result = result
            if self._on_cycle_end is not None:
                to_deliver = self._pending.ids()
                try:
                    await self._on_cycle_end(result, to_deliver)
                    # only what was delivered: an id withdrawn during the await stays
                    self._pending.remove(to_deliver)
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

    def notify_off(self, demand_id: str) -> None:
        """Publish OFF for a withdrawn/expired demand immediately. Threadsafe like
        notify_change; a no-op without an MQTT bridge (HTTP consumers are gated by
        live_demand_view)."""
        if self._on_demand_off is None:
            return

        def _schedule() -> None:
            asyncio.ensure_future(self._off(demand_id))

        try:
            asyncio.get_running_loop()
            _schedule()
        except RuntimeError:
            if self._loop is None:
                log.warning(
                    "notify_off(%s) before loop bound; cycle-end cleanup will cover it",
                    demand_id,
                )
                return
            self._loop.call_soon_threadsafe(_schedule)

    async def _off(self, demand_id: str) -> None:
        try:
            await self._on_demand_off(demand_id)
        except Exception:
            log.exception(
                "publish OFF for %s failed; cycle-end cleanup will cover it", demand_id
            )

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

    def next_cycle_delay(self, now: datetime) -> float:
        """Seconds until the next grid boundary plus cycle_offset_s.

        Cycles fire just after each boundary instead of every `timestep` seconds
        after the previous run, so the cadence does not drift by the solve duration
        and nearest/first/last all resolve to the same anchor at cycle time (e2e
        v0.18.6 observation 3). The boundary whose offset has already passed is
        skipped in favour of the next one.
        """
        step = timedelta(minutes=self._timestep_min)
        target = grid_anchor(now, self._timestep_min, "last") + timedelta(
            seconds=self.cycle_offset_s
        )
        if target <= now:
            target += step
        return (target - now).total_seconds()

    async def run_forever(self) -> None:
        self.bind_loop(asyncio.get_running_loop())
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("cycle crashed; continuing")
            await asyncio.sleep(self.next_cycle_delay(self._clock()))
