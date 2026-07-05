import json
from datetime import datetime, timedelta, timezone

import pytest

from flexd.transports.mqtt_bridge import MqttBridge
from tests.conftest import make_demand
from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler

NOW_REAL = datetime.now(timezone.utc)


class FakePublisher:
    def __init__(self):
        self.published = []  # (topic, payload, retain)

    async def publish(self, topic, payload=None, retain=False, **kw):
        self.published.append((topic, payload, retain))


class FakeStandingRegistryLocal:
    def is_standing(self, demand_id):
        return demand_id == "waterheater"


@pytest.fixture
def bridge(registry):
    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    pub = FakePublisher()
    b = MqttBridge(
        client=pub,
        base_topic="flexd",
        registry=registry,
        view=view,
        scheduler=scheduler,
        standing=FakeStandingRegistryLocal(),
    )
    return b, pub, registry


def demand_json(**kw):
    d = dict(
        energy_target_wh=1200,
        nominal_power_w=2000,
        deadline=(NOW_REAL + timedelta(hours=8)).isoformat(),
        expires_at=(NOW_REAL + timedelta(hours=9)).isoformat(),
    )
    d.update(kw)
    return json.dumps(d)


async def test_intake_set(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", demand_json())
    assert registry.get("dishwasher").source == "loxone"


async def test_intake_invalid_publishes_error(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", "{not json")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert errors == ["flexd/demands/loxone/dishwasher/error"]
    assert registry.get("dishwasher") is None


async def test_intake_delete_clears_retained(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", demand_json())
    await b.handle_message("flexd/demands/loxone/dishwasher/delete", "")
    assert registry.get("dishwasher") is None
    cleared = [(t, p) for t, p, r in pub.published if r and p in (None, "", b"")]
    topics = [t for t, _ in cleared]
    assert "flexd/plan/demands/dishwasher/setpoint" in topics
    assert "flexd/plan/demands/dishwasher/on" in topics


async def test_publish_plan_state(bridge):
    b, pub, registry = bridge
    registry.upsert(make_demand())
    await b.publish_plan(state="ok")
    topics = {t for t, _, _ in pub.published}
    assert "flexd/plan/state" in topics
    assert "flexd/plan/demands/dishwasher/setpoint" in topics
    assert "flexd/plan/demands/dishwasher/on" in topics
    assert all(r for _, _, r in pub.published)  # all retained


async def test_publish_full_plan_when_present(bridge):
    b, pub, registry = bridge
    b._view.adopt(PLAN, {}, now=NOW_REAL)
    b._view.raw_plan = PLAN
    await b.publish_plan(state="ok")
    topics = {t for t, _, _ in pub.published}
    assert "flexd/plan/full" in topics


async def test_cross_source_ownership_error_event(bridge):
    b, pub, registry = bridge
    registry.upsert(make_demand())  # source loxone
    await b.handle_message("flexd/demands/homeassistant/dishwasher/set", demand_json())
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/demands/homeassistant/dishwasher/error" in errors


async def test_standing_squat_error_event(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/waterheater/set", demand_json())
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/demands/loxone/waterheater/error" in errors
    assert registry.get("waterheater") is None


async def test_clear_expired(bridge):
    b, pub, registry = bridge
    await b.clear_expired(["gone-demand"])
    cleared = [t for t, p, r in pub.published if r and p in (None, "", b"")]
    assert "flexd/plan/demands/gone-demand/setpoint" in cleared
    assert "flexd/plan/demands/gone-demand/on" in cleared


async def test_foreign_topic_ignored(bridge):
    b, pub, registry = bridge
    await b.handle_message("other/topic/entirely", "x")
    await b.handle_message("flexd/plan/state", "x")  # own publish topic, not intake
    assert pub.published == []
