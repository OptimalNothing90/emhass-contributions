def test_simple_register_and_setpoint(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone",
            id="spuelmaschine",
            energy_wh=1200,
            power_w=2000,
            deadline_in_h=8,
        ),
    )
    assert r.status_code == 201
    assert r.text == "1"
    # no plan adopted yet -> setpoint 0, plain text
    r = client.get("/simple/demands/spuelmaschine/setpoint")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "0"
    assert client.get("/simple/demands/spuelmaschine/on").text == "0"


def test_simple_hours_only(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(source="loxone", id="pool", power_w=750, hours=4, deadline_in_h=10),
    )
    assert r.status_code == 201


def test_simple_energy_wins_over_hours(client, registry):
    client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone",
            id="pool",
            power_w=750,
            hours=4,
            energy_wh=1500,
            deadline_in_h=10,
        ),
    )
    assert registry.get("pool").energy_target_wh == 1500


def test_simple_done_and_refresh(client):
    client.post(
        "/simple/demands/register",
        params=dict(source="loxone", id="pool", power_w=750, hours=4, deadline_in_h=10),
    )
    assert (
        client.post("/simple/demands/pool/refresh", params={"source": "loxone"}).text
        == "1"
    )
    assert (
        client.post("/simple/demands/pool/done", params={"source": "loxone"}).text
        == "1"
    )
    r = client.get("/simple/demands/pool/setpoint")
    assert r.status_code == 200
    assert r.text == "0"


def test_simple_status(client):
    assert client.get("/simple/status").text in {"ok", "stale", "no-run", "down"}


def test_simple_register_missing_power_400(client):
    r = client.post(
        "/simple/demands/register", params=dict(source="loxone", id="x", hours=4)
    )
    assert r.status_code == 400


def test_simple_register_missing_energy_and_hours_400(client):
    r = client.post(
        "/simple/demands/register", params=dict(source="loxone", id="x", power_w=500)
    )
    assert r.status_code == 400


def test_simple_squat_guard_409(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone", id="waterheater", power_w=3000, hours=2, deadline_in_h=4
        ),
    )
    assert r.status_code == 409


def test_simple_wrong_source_conflict(client):
    client.post(
        "/simple/demands/register",
        params=dict(source="loxone", id="pool", power_w=750, hours=4, deadline_in_h=10),
    )
    assert (
        client.post("/simple/demands/pool/done", params={"source": "ha"}).status_code
        == 409
    )
    assert (
        client.post("/simple/demands/pool/refresh", params={"source": "ha"}).status_code
        == 409
    )


def test_simple_negative_power_422(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(source="loxone", id="neg", power_w=-100, hours=2),
    )
    assert r.status_code == 422


def test_simple_setpoint_never_404(client):
    assert client.get("/simple/demands/ghost/setpoint").text == "0"
    assert client.get("/simple/demands/ghost/on").text == "0"


def test_template_start_simple(client_with_templates):
    assert (
        client_with_templates.post(
            "/simple/templates/dishwasher/start?source=loxone"
        ).text
        == "1"
    )
    assert (
        client_with_templates.post(
            "/simple/templates/ghost/start?source=loxone"
        ).status_code
        == 404
    )


def test_simple_template_retrigger_foreign_source_409(client_with_templates):
    assert (
        client_with_templates.post(
            "/simple/templates/dishwasher/start?source=loxone"
        ).status_code
        == 201
    )
    assert (
        client_with_templates.post(
            "/simple/templates/dishwasher/start?source=ha"
        ).status_code
        == 409
    )


def test_simple_standing_done_routes_to_mark_done(client, standing_fake):
    assert (
        client.post(
            "/simple/demands/waterheater/done", params={"source": "config"}
        ).text
        == "1"
    )
    assert standing_fake.done == ["waterheater"]


def test_simple_standing_done_foreign_source_409(client):
    assert (
        client.post(
            "/simple/demands/waterheater/done", params={"source": "loxone"}
        ).status_code
        == 409
    )


def test_simple_status_down(registry):
    from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler
    from flexd.transports.rest_api import create_app
    from fastapi.testclient import TestClient

    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    scheduler.last_result = "down"
    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=FakeDriver(result=PLAN),
    )
    down_client = TestClient(app)
    assert down_client.get("/simple/status").text == "down"


def test_simple_infinity_power_422(client, registry):
    # #1 HIGH 3: query-string float coercion admits Infinity too
    r = client.post(
        "/simple/demands/register",
        params=dict(source="loxone", id="inf", power_w="Infinity", energy_wh=1000),
    )
    assert r.status_code == 422
    assert registry.get("inf") is None


def test_simple_infinity_deadline_422_not_500(client):
    # timedelta(hours=inf) raises OverflowError inside the handler without the guard
    r = client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone",
            id="inf",
            power_w=2000,
            energy_wh=1000,
            deadline_in_h="Infinity",
        ),
    )
    assert r.status_code == 422


# -- Codex review 2026-10-16 finding 6: finite-but-absurd horizons overflowed timedelta --
def test_simple_huge_finite_deadline_422_not_500(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone",
            id="huge",
            power_w=2000,
            energy_wh=1000,
            deadline_in_h="1e308",
        ),
    )
    assert r.status_code == 422


def test_simple_huge_window_start_422_not_500(client):
    r = client.post(
        "/simple/demands/register",
        params=dict(
            source="loxone",
            id="huge",
            power_w=2000,
            energy_wh=1000,
            window_start_in_h="1e300",
        ),
    )
    assert r.status_code == 422


# -- Codex review 2026-10-16 finding 3: reads are gated by the registry, not the last plan --
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from flexd.plan_view import DemandView
from flexd.transports.rest_api import create_app
from tests.conftest import FakeStandingRegistry, make_demand
from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler


class OnView(FakeView):
    """Adopted plan says 2000 W for every known id; the registry must be the gate."""

    def demand_view(self, demand_id, now):
        return DemandView(setpoint_w=2000.0, on=True, clamped=False)


def _app_with_on_view(registry):
    view = OnView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=FakeDriver(result=PLAN),
        standing=FakeStandingRegistry(),
    )
    return TestClient(app), scheduler


def _client_with_on_view(registry):
    return _app_with_on_view(registry)[0]


def test_withdrawn_demand_reads_off_before_next_solve(registry):
    c = _client_with_on_view(registry)
    registry.upsert(make_demand(id="dishwasher"))
    assert c.get("/simple/demands/dishwasher/setpoint").text == "2000"
    assert c.get("/simple/demands/dishwasher/on").text == "1"
    assert c.post("/simple/demands/dishwasher/done?source=loxone").status_code == 200
    assert c.get("/simple/demands/dishwasher/setpoint").text == "0"
    assert c.get("/simple/demands/dishwasher/on").text == "0"


def test_expired_demand_reads_off_before_sweep(registry):
    c = _client_with_on_view(registry)
    now = datetime.now(timezone.utc)
    registry.upsert(
        make_demand(
            id="dishwasher",
            deadline=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
    )
    assert c.get("/simple/demands/dishwasher/on").text == "0"
    assert c.get("/simple/demands/dishwasher/setpoint").text == "0"


def test_unknown_demand_reads_off(registry):
    c = _client_with_on_view(registry)
    assert c.get("/simple/demands/ghost/on").text == "0"


def test_simple_done_triggers_notify_off(registry, monkeypatch):
    c, scheduler = _app_with_on_view(registry)
    calls = []
    monkeypatch.setattr(scheduler, "notify_off", lambda i: calls.append(i))
    registry.upsert(make_demand(id="dishwasher"))
    assert c.post("/simple/demands/dishwasher/done?source=loxone").status_code == 200
    assert calls == ["dishwasher"]


def test_simple_standing_done_triggers_notify_off(registry, monkeypatch):
    c, scheduler = _app_with_on_view(registry)
    calls = []
    monkeypatch.setattr(scheduler, "notify_off", lambda i: calls.append(i))
    assert c.post("/simple/demands/waterheater/done?source=config").status_code == 200
    assert calls == ["waterheater"]
