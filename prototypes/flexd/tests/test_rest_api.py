from datetime import datetime, timedelta, timezone

from tests.conftest import _payload, make_demand
from tests.test_simple_api import _app_with_on_view, _client_with_on_view


def test_crud_roundtrip(client):
    assert client.post("/api/v1/demands", json=_payload()).status_code == 201
    assert client.get("/api/v1/demands").json()[0]["id"] == "dishwasher"
    r = client.put("/api/v1/demands/dishwasher", json=_payload(energy_target_wh=900))
    assert r.status_code == 200
    assert r.json()["energy_target_wh"] == 900
    assert client.delete("/api/v1/demands/dishwasher?source=loxone").status_code == 204


def test_cross_source_conflict_409(client):
    client.post("/api/v1/demands", json=_payload())
    r = client.post("/api/v1/demands", json=_payload(source="homeassistant"))
    assert r.status_code == 409


def test_invalid_demand_422(client):
    r = client.post("/api/v1/demands", json={"id": "x"})
    assert r.status_code == 422  # pydantic detail passthrough


def test_delete_wrong_source_409(client):
    client.post("/api/v1/demands", json=_payload())
    assert client.delete("/api/v1/demands/dishwasher?source=ha").status_code == 409


def test_delete_unknown_404(client):
    assert client.delete("/api/v1/demands/ghost?source=loxone").status_code == 404


def test_put_id_mismatch_400(client):
    r = client.put("/api/v1/demands/other", json=_payload())
    assert r.status_code == 400


def test_standing_id_squat_409(client):
    r = client.post("/api/v1/demands", json=_payload(id="waterheater"))
    assert r.status_code == 409
    assert "standing" in r.json()["detail"]


def test_standing_id_post_config_source_409(client):
    r = client.post("/api/v1/demands", json=_payload(id="waterheater", source="config"))
    assert r.status_code == 409
    assert "PUT" in r.json()["detail"]


def test_plan_no_run(client):
    r = client.get("/api/v1/plan")
    assert r.status_code == 200
    assert r.json()["flexd_meta"]["state"] == "no-run"


def test_plan_demand_unknown_404(client):
    assert client.get("/api/v1/plan/demands/ghost").status_code == 404


def test_plan_demand_pending_200(client):
    client.post("/api/v1/demands", json=_payload())
    r = client.get("/api/v1/plan/demands/dishwasher")
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] is True
    assert body["setpoint_w"] == 0
    assert body["on"] is False


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_manual_cycle(client):
    r = client.post("/api/v1/cycle")
    assert r.status_code == 200
    assert r.json()["result"] in {"ok", "skipped", "rejected", "down"}


def test_openapi_served(client):
    assert client.get("/openapi.json").status_code == 200


def test_refresh_bumps_expiry(client):
    client.post("/api/v1/demands", json=_payload())
    before = client.get("/api/v1/demands").json()[0]["expires_at"]
    r = client.post("/api/v1/demands/dishwasher/refresh?source=loxone")
    assert r.status_code == 200
    assert r.json()["expires_at"] > before
    assert (
        client.post("/api/v1/demands/dishwasher/refresh?source=ha").status_code == 409
    )
    assert client.post("/api/v1/demands/ghost/refresh?source=loxone").status_code == 404


def test_template_start_rest(client_with_templates):
    r = client_with_templates.post(
        "/api/v1/templates/dishwasher/start", json={"source": "ha"}
    )
    assert r.status_code == 201
    assert r.json()["id"] == "dishwasher"
    assert (
        client_with_templates.post(
            "/api/v1/templates/ghost/start", json={"source": "ha"}
        ).status_code
        == 404
    )


def test_template_retrigger_foreign_source_409(client_with_templates):
    r = client_with_templates.post(
        "/api/v1/templates/dishwasher/start", json={"source": "ha"}
    )
    assert r.status_code == 201
    r = client_with_templates.post(
        "/api/v1/templates/dishwasher/start", json={"source": "loxone"}
    )
    assert r.status_code == 409


def test_standing_delete_routes_to_mark_done(client, standing_fake):
    r = client.delete("/api/v1/demands/waterheater?source=config")
    assert r.status_code == 204
    assert standing_fake.done == ["waterheater"]


def test_standing_delete_foreign_source_409(client):
    assert client.delete("/api/v1/demands/waterheater?source=loxone").status_code == 409


def test_standing_put_config_is_correction(client, standing_fake):
    payload = _payload(
        id="waterheater", source="config", energy_target_wh=3000, nominal_power_w=3000
    )
    r = client.put("/api/v1/demands/waterheater", json=payload)
    assert r.status_code == 200
    assert r.json()["corrected"] is True
    assert standing_fake.corrections == [("waterheater", 1.0)]


def test_infinity_body_422_and_not_persisted(client, registry):
    # #1 HIGH 3: raw string body — json= would serialize inf as Infinity too, but be explicit
    body = (
        '{"id":"dishwasher","source":"loxone","energy_target_wh":1200,'
        '"nominal_power_w":Infinity,'
        '"deadline":"2099-01-01T00:00:00Z","expires_at":"2099-01-01T01:00:00Z"}'
    )
    r = client.post(
        "/api/v1/demands", content=body, headers={"content-type": "application/json"}
    )
    assert r.status_code == 422
    # stock FastAPI handler echoes input=inf and 500s in the serializer; the body
    # must still name the field and the reason
    assert r.json()["detail"][0]["loc"] == ["body", "nominal_power_w"]
    assert "finite" in r.json()["detail"][0]["msg"]
    assert registry.get("dishwasher") is None


# -- Codex review 2026-10-16 finding 6: the 422 body must not echo request input --
def test_422_body_does_not_echo_input(client):
    body = (
        '{"id":"dishwasher","source":"loxone","energy_target_wh":1200,'
        '"nominal_power_w":Infinity,"note":"do-not-echo-me",'
        '"deadline":"2099-01-01T00:00:00Z","expires_at":"2099-01-01T01:00:00Z"}'
    )
    r = client.post(
        "/api/v1/demands", content=body, headers={"content-type": "application/json"}
    )
    assert r.status_code == 422
    text = r.text
    assert "do-not-echo-me" not in text
    detail = r.json()["detail"]
    assert all(set(err) <= {"loc", "msg", "type"} for err in detail)
    assert ["body", "nominal_power_w"] in [err["loc"] for err in detail]


# -- Codex review 2026-10-16 finding 3: plan read-back gated by the registry --


def test_plan_demand_expired_is_off_not_on(registry):
    c = _client_with_on_view(registry)
    now = datetime.now(timezone.utc)
    registry.upsert(
        make_demand(
            deadline=now - timedelta(hours=2), expires_at=now - timedelta(hours=1)
        )
    )
    r = c.get("/api/v1/plan/demands/dishwasher")
    assert r.status_code == 200
    assert r.json()["on"] is False
    assert r.json()["setpoint_w"] == 0
    assert r.json()["expired"] is True


def test_plan_demand_withdrawn_is_404(registry):
    c = _client_with_on_view(registry)
    registry.upsert(make_demand())
    assert c.delete("/api/v1/demands/dishwasher?source=loxone").status_code == 204
    assert c.get("/api/v1/plan/demands/dishwasher").status_code == 404


def test_rest_withdraw_triggers_notify_off(registry, monkeypatch):
    c, scheduler = _app_with_on_view(registry)
    calls = []
    monkeypatch.setattr(scheduler, "notify_off", lambda i: calls.append(i))
    registry.upsert(make_demand())
    assert c.delete("/api/v1/demands/dishwasher?source=loxone").status_code == 204
    assert calls == ["dishwasher"]


def test_rest_standing_withdraw_triggers_notify_off(registry, monkeypatch):
    c, scheduler = _app_with_on_view(registry)
    calls = []
    monkeypatch.setattr(scheduler, "notify_off", lambda i: calls.append(i))
    assert c.delete("/api/v1/demands/waterheater?source=config").status_code == 204
    assert calls == ["waterheater"]


# -- #1 Medium 12: a client must not grow the registry and the MILP without limit --
def _client_with_capacity(tmp_path, max_demands):
    from fastapi.testclient import TestClient

    from flexd.registry import Registry
    from flexd.transports.rest_api import create_app
    from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler

    registry = Registry(tmp_path / "demands.json", max_demands=max_demands)
    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=FakeDriver(result=PLAN),
    )
    return TestClient(app), registry


def test_rest_register_beyond_max_demands_409(tmp_path):
    c, registry = _client_with_capacity(tmp_path, max_demands=1)
    assert c.post("/api/v1/demands", json=_payload(id="first")).status_code == 201
    r = c.post("/api/v1/demands", json=_payload(id="second"))
    assert r.status_code == 409
    assert "max_demands" in r.json()["detail"]
    assert registry.get("second") is None
    r = c.put("/api/v1/demands/second", json=_payload(id="second"))
    assert r.status_code == 409


def test_simple_register_beyond_max_demands_409(tmp_path):
    c, registry = _client_with_capacity(tmp_path, max_demands=1)
    params = dict(source="loxone", power_w=2000, energy_wh=1000)
    first = c.post("/simple/demands/register", params={**params, "id": "a"})
    assert first.status_code == 201
    r = c.post("/simple/demands/register", params={**params, "id": "b"})
    assert r.status_code == 409
    assert registry.get("b") is None


# -- #1 Lows: typo'd field is a 422, oversized or length-less bodies are refused --
def test_unknown_field_422(client, registry):
    r = client.post("/api/v1/demands", json=_payload(p_min_watt=500))
    assert r.status_code == 422
    assert ["body", "p_min_watt"] in [err["loc"] for err in r.json()["detail"]]
    assert registry.get("dishwasher") is None


def test_body_above_64kib_is_413(client, registry):
    body = _payload()
    body["note"] = "x" * (64 * 1024)
    r = client.post("/api/v1/demands", json=body)
    assert r.status_code == 413
    assert registry.get("dishwasher") is None


def test_body_within_limit_still_registers(client):
    assert client.post("/api/v1/demands", json=_payload()).status_code == 201


def test_chunked_body_without_length_is_411(client, registry):
    import json as _json

    def chunks():
        yield _json.dumps(_payload()).encode()

    r = client.post(
        "/api/v1/demands",
        content=chunks(),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 411
    assert registry.get("dishwasher") is None


# -- #1 Lows: withdraw racing a template re-trigger ---------------------------------
def _client_with_templates_over(registry):
    from fastapi.testclient import TestClient

    from flexd.templates import TemplateManager
    from flexd.transports.rest_api import create_app
    from tests.conftest import FakeStandingRegistry
    from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler
    from tests.test_templates import TPL

    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    templates = TemplateManager([TPL], tz="UTC", registry=registry, default_ttl_s=3600)
    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=FakeDriver(result=PLAN),
        standing=FakeStandingRegistry(),
        templates=templates,
    )
    return TestClient(app)


def test_template_retrigger_racing_withdraw_is_409_not_404(tmp_path):
    from tests.test_templates import WithdrawnMidRefresh

    client = _client_with_templates_over(WithdrawnMidRefresh(tmp_path / "d.json"))
    assert (
        client.post(
            "/api/v1/templates/dishwasher/start", json={"source": "ha"}
        ).status_code
        == 201
    )
    r = client.post("/api/v1/templates/dishwasher/start", json={"source": "ha"})
    assert r.status_code == 409
    assert "withdrawn" in r.json()["detail"]
    # a truly unknown template stays 404
    assert (
        client.post("/api/v1/templates/ghost/start", json={"source": "ha"}).status_code
        == 404
    )
