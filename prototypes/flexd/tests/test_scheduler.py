import asyncio
from datetime import datetime, timedelta, timezone

from flexd.emhass_driver import PlanRejected
from flexd.scheduler import Scheduler
from tests.conftest import make_demand

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)


class FakeDriver:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    async def run_cycle(self, payload, last_generated_at=None):
        self.calls.append(payload)
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


class FakeStanding:
    def materialize(self, now, elapsed_lookup):
        pass


PLAN = {
    "status": "ok",
    "generated_at": "2026-07-05T12:00:05Z",
    "emhass_schema_version": "1.0",
    "plan": [],
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
    s = make_scheduler(registry, driver, view)
    seen = []

    async def on_end(state, swept_ids):
        seen.append((state, swept_ids))

    s._on_cycle_end = on_end
    result = await s.run_once(now=NOW)
    assert result == "skipped"  # only demand was expired
    assert seen == [("skipped", ["old"])]


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
