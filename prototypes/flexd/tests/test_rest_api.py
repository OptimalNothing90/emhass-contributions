from tests.conftest import _payload


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
