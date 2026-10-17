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
    def __init__(self):
        self.done = []
        self.corrections = []

    def is_standing(self, demand_id):
        return demand_id == "waterheater"

    def mark_done(self, demand_id, now):
        self.done.append(demand_id)

    def correct(self, demand_id, *, remaining_hours, now):
        self.corrections.append((demand_id, remaining_hours))


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


@pytest.fixture
def bridge_with_templates(registry):
    from tests.test_templates import TPL
    from flexd.templates import TemplateManager

    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    pub = FakePublisher()
    templates = TemplateManager([TPL], tz="UTC", registry=registry, default_ttl_s=3600)
    b = MqttBridge(
        client=pub,
        base_topic="flexd",
        registry=registry,
        view=view,
        scheduler=scheduler,
        standing=FakeStandingRegistryLocal(),
        templates=templates,
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


async def test_intake_non_object_json_publishes_error(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", "[1,2,3]")
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


async def test_standing_delete_requires_config_source(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/waterheater/delete", "")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/demands/loxone/waterheater/error" in errors
    assert b._standing.done == []


async def test_standing_delete_config_source_marks_done(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/config/waterheater/delete", "")
    assert b._standing.done == ["waterheater"]


async def test_delete_unknown_is_idempotent_no_error(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/ghost/delete", "")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert errors == []


async def test_intake_refresh_bumps_expiry(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", demand_json())
    old = registry.get("dishwasher").expires_at
    await b.handle_message("flexd/demands/loxone/dishwasher/refresh", "")
    assert registry.get("dishwasher").expires_at > old


async def test_intake_refresh_foreign_source_error_event(bridge):
    b, pub, registry = bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", demand_json())
    await b.handle_message("flexd/demands/homeassistant/dishwasher/refresh", "")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/demands/homeassistant/dishwasher/error" in errors


async def test_topic_wins_over_payload_identity(bridge):
    b, pub, registry = bridge
    await b.handle_message(
        "flexd/demands/loxone/dishwasher/set", demand_json(id="other", source="evil")
    )
    assert registry.get("dishwasher").source == "loxone"
    assert registry.get("other") is None


async def test_clear_expired(bridge):
    b, pub, registry = bridge
    await b.clear_expired(["gone-demand"])
    cleared = [t for t, p, r in pub.published if r and p in (None, "", b"")]
    assert "flexd/plan/demands/gone-demand/setpoint" in cleared
    assert "flexd/plan/demands/gone-demand/on" in cleared


async def test_clear_expired_publishes_off_before_clearing_even_when_never_mapped(
    bridge,
):
    # #1 Medium 11 remainder: an id withdrawn before it was ever mapped gets no
    # mapped-but-inactive OFF from publish_plan; the clear itself must say OFF first
    b, pub, registry = bridge
    assert "never-mapped" not in b._view.mapped_ids()
    await b.clear_expired(["never-mapped"])
    seq = [
        (t.rsplit("/", 1)[1], p)
        for t, p, r in pub.published
        if t.startswith("flexd/plan/demands/never-mapped/") and r
    ]
    assert seq == [("setpoint", "0"), ("on", "0"), ("setpoint", ""), ("on", "")]


async def test_foreign_topic_ignored(bridge):
    b, pub, registry = bridge
    await b.handle_message("other/topic/entirely", "x")
    await b.handle_message("flexd/plan/state", "x")  # own publish topic, not intake
    assert pub.published == []


async def test_template_start_via_mqtt(bridge_with_templates):
    b, pub, registry = bridge_with_templates
    await b.handle_message("flexd/templates/ha/dishwasher/start", "")
    assert registry.get("dishwasher") is not None


async def test_template_unknown_error_event(bridge_with_templates):
    b, pub, registry = bridge_with_templates
    await b.handle_message("flexd/templates/ha/ghost/start", "")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/templates/ha/ghost/error" in errors


async def test_standing_set_config_source_is_correction(bridge):
    b, pub, registry = bridge
    await b.handle_message(
        "flexd/demands/config/waterheater/set",
        demand_json(energy_target_wh=3000, nominal_power_w=3000),
    )
    assert b._standing.corrections == [("waterheater", 1.0)]
    assert registry.get("waterheater") is None


async def test_standing_set_config_zero_power_error_event(bridge):
    b, pub, registry = bridge
    await b.handle_message(
        "flexd/demands/config/waterheater/set",
        demand_json(energy_target_wh=3000, nominal_power_w=0),
    )
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "flexd/demands/config/waterheater/error" in errors
    assert b._standing.corrections == []


async def test_set_with_infinity_publishes_error_and_registers_nothing(bridge):
    # #1 HIGH 3: json.loads accepts the Infinity token; the model must reject it
    b, pub, registry = bridge
    payload = (
        '{"energy_target_wh":1200,"nominal_power_w":Infinity,'
        f'"deadline":"{(NOW_REAL + timedelta(hours=8)).isoformat()}",'
        f'"expires_at":"{(NOW_REAL + timedelta(hours=9)).isoformat()}"}}'
    )
    await b.handle_message("flexd/demands/loxone/inf/set", payload)
    assert registry.get("inf") is None
    topics = [t for t, _, _ in pub.published]
    assert "flexd/demands/loxone/inf/error" in topics


# -- Codex review 2026-10-16 finding 3 / plan review finding 1: explicit retained OFF --
async def test_delete_publishes_off_before_clearing(bridge):
    b, pub, registry = bridge
    registry.upsert(make_demand())
    pub.published.clear()
    await b.handle_message("flexd/demands/loxone/dishwasher/delete", "")
    on_msgs = [
        p for t, p, _ in pub.published if t == "flexd/plan/demands/dishwasher/on"
    ]
    sp_msgs = [
        p for t, p, _ in pub.published if t == "flexd/plan/demands/dishwasher/setpoint"
    ]
    assert (
        on_msgs[:1] == ["0"] and "" in on_msgs
    )  # OFF first, then the empty-payload clear
    assert sp_msgs[:1] == ["0"] and "" in sp_msgs


async def test_publish_plan_sends_off_for_mapped_but_expired_demand(bridge):
    b, pub, registry = bridge
    now = datetime.now(timezone.utc)
    registry.upsert(
        make_demand(
            deadline=now - timedelta(hours=2), expires_at=now - timedelta(hours=1)
        )
    )
    b._view.adopt(
        PLAN,
        {"dishwasher": {"slot": 0, "clamped": False, "nominal_power_w": 2000}},
        now=now,
    )
    await b.publish_plan(state="ok")
    assert ("flexd/plan/demands/dishwasher/on", "0", True) in pub.published
    assert ("flexd/plan/demands/dishwasher/setpoint", "0", True) in pub.published


# -- #1 Medium 10: a multi-segment base_topic silently dropped every message --
@pytest.fixture
def nested_bridge(registry):
    from flexd.templates import TemplateManager
    from tests.test_templates import TPL

    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    pub = FakePublisher()
    templates = TemplateManager([TPL], tz="UTC", registry=registry, default_ttl_s=3600)
    b = MqttBridge(
        client=pub,
        base_topic="home/flexd",
        registry=registry,
        view=view,
        scheduler=scheduler,
        standing=FakeStandingRegistryLocal(),
        templates=templates,
    )
    return b, pub, registry


async def test_nested_base_demand_set_delete(nested_bridge):
    b, pub, registry = nested_bridge
    await b.handle_message("home/flexd/demands/loxone/dishwasher/set", demand_json())
    assert registry.get("dishwasher").source == "loxone"
    await b.handle_message("home/flexd/demands/loxone/dishwasher/delete", "")
    assert registry.get("dishwasher") is None
    assert ("home/flexd/plan/demands/dishwasher/on", "0", True) in pub.published


async def test_nested_base_template_start_and_error(nested_bridge):
    b, pub, registry = nested_bridge
    await b.handle_message("home/flexd/templates/ha/dishwasher/start", "")
    assert registry.get("dishwasher") is not None
    await b.handle_message("home/flexd/templates/ha/ghost/start", "")
    errors = [t for t, _, _ in pub.published if t.endswith("/error")]
    assert "home/flexd/templates/ha/ghost/error" in errors


async def test_nested_base_ignores_partial_prefix_and_own_topics(nested_bridge):
    b, pub, registry = nested_bridge
    await b.handle_message("flexd/demands/loxone/dishwasher/set", demand_json())
    await b.handle_message("home/flexd/plan/state", "x")
    await b.handle_message("home/flexdx/demands/loxone/dishwasher/set", demand_json())
    assert registry.get("dishwasher") is None
    assert pub.published == []


# -- #1 Medium 12: registry capacity surfaces as an error event --
async def test_set_beyond_max_demands_publishes_error(tmp_path):
    from flexd.registry import Registry

    registry = Registry(tmp_path / "demands.json", max_demands=1)
    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    pub = FakePublisher()
    b = MqttBridge(
        client=pub,
        base_topic="flexd",
        registry=registry,
        view=view,
        scheduler=scheduler,
    )
    await b.handle_message("flexd/demands/loxone/first/set", demand_json())
    await b.handle_message("flexd/demands/loxone/second/set", demand_json())
    assert registry.get("second") is None
    errors = [(t, p) for t, p, _ in pub.published if t.endswith("/error")]
    assert errors and errors[0][0] == "flexd/demands/loxone/second/error"
    assert "max_demands" in errors[0][1]


# -- #1 Lows: an unknown key in a set payload is an error event, not a silent drop --
async def test_set_with_unknown_key_publishes_error(bridge):
    b, pub, registry = bridge
    await b.handle_message(
        "flexd/demands/loxone/dishwasher/set", demand_json(p_min_watt=500)
    )
    assert registry.get("dishwasher") is None
    errors = [(t, p) for t, p, _ in pub.published if t.endswith("/error")]
    assert errors and "p_min_watt" in errors[0][1]


# -- #1 Lows: withdraw racing a template re-trigger ---------------------------------
async def test_template_retrigger_racing_withdraw_publishes_error_event(tmp_path):
    from flexd.templates import TemplateManager
    from tests.test_templates import TPL, WithdrawnMidRefresh

    registry = WithdrawnMidRefresh(tmp_path / "d.json")
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
        templates=TemplateManager(
            [TPL], tz="UTC", registry=registry, default_ttl_s=3600
        ),
    )
    await b.handle_message("flexd/templates/loxone/dishwasher/start", "")
    await b.handle_message("flexd/templates/loxone/dishwasher/start", "")
    errors = [
        json.loads(p)
        for t, p, r in pub.published
        if t == "flexd/templates/loxone/dishwasher/error"
    ]
    assert len(errors) == 1
    assert "withdrawn" in errors[0]["error"]
