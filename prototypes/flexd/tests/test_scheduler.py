import asyncio
from datetime import datetime, timedelta, timezone

from flexd.emhass_driver import PlanRejected
from flexd.scheduler import Scheduler
from tests.conftest import make_demand

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)


class FakeDriver:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []
        self.kwargs = []  # what the scheduler handed the driver besides the payload

    async def run_cycle(self, payload, last_generated_at=None, **kw):
        self.calls.append(payload)
        self.kwargs.append({"last_generated_at": last_generated_at, **kw})
        if self.error:
            raise self.error
        return self.result


class FakeView:
    def __init__(self):
        self.adopted = []
        self.generated_at = None
        self.raw_plan = None

    def adopt(self, plan, mapping, now):
        self.adopted.append((plan, mapping))

    def on_hours_elapsed(self, i, s, u):
        return 0.0

    def state(self, now):
        return "ok" if self.adopted else "no-run"

    def demand_view(self, demand_id, now):
        return None

    def mapped_ids(self):
        return set(self.adopted[-1][1]) if self.adopted else set()


class FakeStanding:
    def materialize(self, now, elapsed_lookup):
        pass

    def accrue(self, now, elapsed_lookup):
        pass


PLAN = {
    "status": "ok",
    "generated_at": "2026-07-05T12:00:05Z",
    "emhass_schema_version": "1.0",
    # one slot on the 30-min grid anchored at NOW: what a solve for one demand returns
    # (the structural check rejects an empty plan, #1 Medium 9)
    "plan": [
        {"timestamp": "2026-07-05T12:00:00Z", "P_deferrable0": 2000},
        {"timestamp": "2026-07-05T12:30:00Z", "P_deferrable0": 0},
    ],
}


def make_scheduler(registry, driver, view):
    return Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
    )


async def test_cycle_adopts_plan(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    driver, view = FakeDriver(result=PLAN), FakeView()
    s = make_scheduler(registry, driver, view)
    result = await s.run_once(now=NOW)
    assert result == "ok"
    assert len(view.adopted) == 1
    assert driver.calls[0]["number_of_deferrable_loads"] == 1


async def test_cycle_skips_without_demands(registry):
    driver, view = FakeDriver(result=PLAN), FakeView()
    s = make_scheduler(registry, driver, view)
    result = await s.run_once(now=NOW)
    assert result == "skipped"
    assert driver.calls == []


async def test_rejected_plan_not_adopted(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    driver, view = FakeDriver(error=PlanRejected("no-run")), FakeView()
    s = make_scheduler(registry, driver, view)
    result = await s.run_once(now=NOW)
    assert result == "rejected"
    assert view.adopted == []


async def test_emhass_down_result(registry):
    import httpx

    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    driver, view = FakeDriver(error=httpx.ConnectError("down")), FakeView()
    s = make_scheduler(registry, driver, view)
    result = await s.run_once(now=NOW)
    assert result == "down"
    assert view.adopted == []


async def test_expired_swept_and_reported(registry):
    registry.upsert(
        make_demand(
            id="old",
            expires_at=NOW - timedelta(seconds=1),
            deadline=NOW - timedelta(seconds=2),
        )
    )
    driver, view = FakeDriver(result=PLAN), FakeView()
    seen = []

    async def on_end(state, swept_ids):
        seen.append((state, swept_ids))

    s = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        on_cycle_end=on_end,
    )
    result = await s.run_once(now=NOW)
    assert result == "skipped"  # only demand was expired
    assert seen == [("skipped", ["old"])]


async def test_deleted_demand_funneled_into_on_cycle_end(registry):
    registry.upsert(
        make_demand(
            id="withdrawn",
            deadline=NOW + timedelta(hours=4),
            expires_at=NOW + timedelta(hours=5),
        )
    )
    registry.delete("withdrawn", source="loxone")
    driver, view = FakeDriver(result=PLAN), FakeView()
    seen = []

    async def on_end(state, swept_ids):
        seen.append((state, swept_ids))

    s = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        on_cycle_end=on_end,
    )
    result = await s.run_once(now=NOW)
    assert result == "skipped"  # the only demand was deleted before the cycle ran
    assert seen == [("skipped", ["withdrawn"])]


async def test_notify_change_debounces(registry):
    # real-clock demand: debounced run_once uses utcnow(), a NOW-pinned demand would be expired
    registry.upsert(make_demand())
    driver, view = FakeDriver(result=PLAN), FakeView()
    s = make_scheduler(registry, driver, view)
    s.debounce_s = 0.05
    s.notify_change()
    s.notify_change()
    await asyncio.sleep(0.15)
    assert len(driver.calls) == 1  # two notifications, one solve


async def test_notify_change_from_thread(registry):
    import threading

    # real-clock demand: debounced run_once uses utcnow(), a NOW-pinned demand would be expired
    registry.upsert(make_demand())
    driver, view = FakeDriver(result=PLAN), FakeView()
    s = make_scheduler(registry, driver, view)
    s.debounce_s = 0.05
    s.bind_loop(asyncio.get_running_loop())
    t = threading.Thread(target=s.notify_change)
    t.start()
    t.join()
    await asyncio.sleep(0.15)
    assert len(driver.calls) == 1


async def test_concurrent_run_once_serialized(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    gate = asyncio.Event()
    order = []

    class BlockingDriver:
        def __init__(self):
            self.calls = 0

        async def run_cycle(self, payload, last_generated_at=None, **kw):
            self.calls += 1
            order.append(f"start{self.calls}")
            if self.calls == 1:
                await gate.wait()
            order.append(f"end{self.calls}")
            return PLAN

    driver, view = BlockingDriver(), FakeView()
    s = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
    )
    t1 = asyncio.create_task(s.run_once(now=NOW))
    await asyncio.sleep(0.05)
    t2 = asyncio.create_task(s.run_once(now=NOW))
    await asyncio.sleep(0.05)
    gate.set()
    await asyncio.gather(t1, t2)
    assert order == ["start1", "end1", "start2", "end2"]  # strictly serialized


async def test_on_cycle_end_failure_keeps_result_and_redelivers(registry):
    registry.upsert(
        make_demand(
            id="old",
            deadline=NOW - timedelta(seconds=2),
            expires_at=NOW - timedelta(seconds=1),
        )
    )
    driver, view = FakeDriver(result=PLAN), FakeView()
    calls = []

    async def flaky(state, swept_ids):
        calls.append(list(swept_ids))
        if len(calls) == 1:
            raise RuntimeError("mqtt down")

    s = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        on_cycle_end=flaky,
    )
    result = await s.run_once(now=NOW)
    assert result == "skipped"  # publish failure never changes the cycle result
    await s.run_once(now=NOW)
    assert calls[0] == ["old"]
    assert calls[1] == ["old"]  # redelivered after failure


async def test_crumb_written_on_skipped(registry, tmp_path):
    import json as _json

    crumb = tmp_path / "last_cycle.json"
    s = Scheduler(
        registry=registry,
        driver=FakeDriver(result=PLAN),
        view=FakeView(),
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        crumb_path=crumb,
    )
    await s.run_once(now=NOW)
    data = _json.loads(crumb.read_text(encoding="utf-8"))
    assert data["result"] == "skipped"
    assert data["payload_sha256"] is None


# -- Codex review 2026-10-16 finding 3 / plan review finding 1: immediate OFF trigger --
async def test_notify_off_invokes_callback(registry):
    seen = []

    async def off(demand_id):
        seen.append(demand_id)

    s = Scheduler(
        registry=registry,
        driver=FakeDriver(result=PLAN),
        view=FakeView(),
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        on_demand_off=off,
    )
    s.notify_off("dishwasher")
    await asyncio.sleep(0)
    assert seen == ["dishwasher"]


# -- Codex review 2026-10-16 finding 4: old plan credited until the real switch --
class RecordingStanding:
    def __init__(self):
        self.accrued = []
        self.materialized = []

    def accrue(self, now, elapsed_lookup):
        self.accrued.append(now)

    def materialize(self, now, elapsed_lookup):
        self.materialized.append(now)


class RecordingView(FakeView):
    def adopt(self, plan, mapping, now):
        self.adopted.append((plan, mapping, now))


async def test_old_plan_accrued_to_adoption_instant_and_adopted_there(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    view, standing = RecordingView(), RecordingStanding()
    ticks = iter([NOW + timedelta(minutes=2, seconds=11)])  # the solver took 2:11
    s = Scheduler(
        registry=registry,
        driver=FakeDriver(result=PLAN),
        view=view,
        standing=standing,
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        clock=lambda: next(ticks),
    )
    assert await s.run_once(now=NOW) == "ok"
    assert standing.materialized == [NOW]  # demands built from cycle start
    assert standing.accrued == [
        NOW + timedelta(minutes=2, seconds=11)
    ]  # old plan credited until the switch
    assert view.adopted[0][2] == NOW + timedelta(
        minutes=2, seconds=11
    )  # new plan effective from the switch


async def test_no_accrue_or_adopt_when_plan_rejected(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    view, standing = RecordingView(), RecordingStanding()
    s = Scheduler(
        registry=registry,
        driver=FakeDriver(error=PlanRejected("stale")),
        view=view,
        standing=standing,
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        clock=lambda: NOW + timedelta(minutes=1),
    )
    assert await s.run_once(now=NOW) == "rejected"
    assert standing.accrued == []
    assert view.adopted == []


# -- plan review finding 3: the scheduler anchors the grid with the configured ts_round --
async def test_scheduler_passes_ts_round_to_aggregation(registry):
    # now 12:01, deadline 13:01: anchor 12:00 (nearest) -> end step 2; anchor 12:30 (last) -> 1
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=1, minutes=1),
            expires_at=NOW + timedelta(hours=2),
        )
    )
    ends = {}
    for ts_round in ("nearest", "last"):
        driver = FakeDriver(result=PLAN)
        s = Scheduler(
            registry=registry,
            driver=driver,
            view=FakeView(),
            standing=FakeStanding(),
            timestep_min=30,
            horizon_steps=48,
            extra_runtime_params={},
            ts_round=ts_round,
        )
        await s.run_once(now=NOW + timedelta(minutes=1))
        ends[ts_round] = driver.calls[0]["end_timesteps_of_each_deferrable_load"][0]
    assert ends == {"nearest": 2, "last": 1}


# -- #1 Medium 7: the driver needs the cycle instant and the step for its first-boot guard --
async def test_scheduler_hands_now_and_timestep_to_driver(registry):
    registry.upsert(
        make_demand(
            deadline=NOW + timedelta(hours=4), expires_at=NOW + timedelta(hours=5)
        )
    )
    driver = FakeDriver(result=PLAN)
    s = make_scheduler(registry, driver, FakeView())
    await s.run_once(now=NOW)
    assert driver.kwargs[0]["now"] == NOW
    assert driver.kwargs[0]["timestep_min"] == 30


# -- #1 Medium 9: the adopted plan must structurally match the submitted payload --
def _plan(records):
    return {**PLAN, "plan": records}


def _ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _run_with_plan(registry, plan, now=NOW, demands=1):
    for n in range(demands):
        registry.upsert(
            make_demand(
                id=f"load-{n}",
                deadline=NOW + timedelta(hours=4),
                expires_at=NOW + timedelta(hours=5),
            )
        )
    view = FakeView()
    s = make_scheduler(registry, FakeDriver(result=plan), view)
    return await s.run_once(now=now), view


async def test_plan_missing_deferrable_column_rejected(registry):
    plan = _plan(
        [
            {"timestamp": _ts(NOW), "P_deferrable0": 2000},
            {"timestamp": _ts(NOW + timedelta(minutes=30)), "P_deferrable0": 0},
        ]
    )
    result, view = await _run_with_plan(registry, plan, demands=2)  # slot 1 absent
    assert result == "rejected"
    assert view.adopted == []


async def test_plan_with_wrong_step_rejected(registry):
    plan = _plan(
        [
            {"timestamp": _ts(NOW), "P_deferrable0": 2000},
            {"timestamp": _ts(NOW + timedelta(minutes=15)), "P_deferrable0": 0},
        ]
    )
    result, view = await _run_with_plan(registry, plan)  # flexd runs a 30-min grid
    assert result == "rejected"
    assert view.adopted == []


async def test_plan_anchored_elsewhere_rejected(registry):
    plan = _plan(
        [
            {"timestamp": _ts(NOW + timedelta(hours=2)), "P_deferrable0": 2000},
            {
                "timestamp": _ts(NOW + timedelta(hours=2, minutes=30)),
                "P_deferrable0": 0,
            },
        ]
    )
    result, view = await _run_with_plan(registry, plan)
    assert result == "rejected"
    assert view.adopted == []


async def test_plan_one_step_off_anchor_still_adopted(registry):
    # grid_anchor's documented limit: a rounding boundary crossed between flexd's now and
    # EMHASS's receipt shifts step 0 by one slot
    plan = _plan(
        [
            {"timestamp": _ts(NOW + timedelta(minutes=30)), "P_deferrable0": 2000},
            {"timestamp": _ts(NOW + timedelta(hours=1)), "P_deferrable0": 0},
        ]
    )
    result, view = await _run_with_plan(registry, plan)
    assert result == "ok"
    assert len(view.adopted) == 1


async def test_plan_without_records_rejected(registry):
    result, view = await _run_with_plan(registry, _plan([]))
    assert result == "rejected"
    assert view.adopted == []


async def test_matching_plan_adopted(registry):
    plan = _plan(
        [
            {"timestamp": _ts(NOW), "P_deferrable0": 2000, "P_deferrable1": 0},
            {
                "timestamp": _ts(NOW + timedelta(minutes=30)),
                "P_deferrable0": 0,
                "P_deferrable1": 3000,
            },
        ]
    )
    result, view = await _run_with_plan(registry, plan, demands=2)
    assert result == "ok"


# -- #1 Lows: _pending_swept grew without bound across a long broker outage --
async def test_pending_swept_keeps_only_the_last_1000_ids(registry):
    registry.upsert(
        make_demand(
            id="old",
            deadline=NOW - timedelta(seconds=2),
            expires_at=NOW - timedelta(seconds=1),
        )
    )
    delivered = []

    async def failing(state, swept_ids):
        delivered.append(list(swept_ids))
        raise RuntimeError("broker down")

    s = Scheduler(
        registry=registry,
        driver=FakeDriver(result=PLAN),
        view=FakeView(),
        standing=FakeStanding(),
        timestep_min=30,
        horizon_steps=48,
        extra_runtime_params={},
        on_cycle_end=failing,
    )
    s._pending_swept = [f"ghost-{i}" for i in range(1500)]  # backlog from the outage
    await s.run_once(now=NOW)
    assert len(delivered[0]) == 1000
    assert delivered[0][-1] == "old"  # newest kept, oldest dropped
    assert delivered[0][0] == "ghost-501"
