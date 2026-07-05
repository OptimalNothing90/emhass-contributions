import json
from pathlib import Path

import httpx
import pytest
import respx

from flexd.emhass_driver import EmhassDriver, PlanRejected

FIX = Path(__file__).parent / "fixtures"
BASE = "http://emhass:5000"


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture
def driver():
    return EmhassDriver(BASE, known_schema_versions={"1.0"})


@respx.mock
async def test_run_cycle_ok(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(201, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    plan = await driver.run_cycle({"prediction_horizon": 48})
    assert plan["status"] == "ok"
    assert len(plan["plan"]) == 2


@respx.mock
async def test_no_run_raises(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(201, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_no_run.json"))
    with pytest.raises(PlanRejected, match="no-run"):
        await driver.run_cycle({})


@respx.mock
async def test_unknown_schema_rejected(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(201, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_bad_schema.json"))
    with pytest.raises(PlanRejected, match="schema"):
        await driver.run_cycle({})


@respx.mock
async def test_stale_generated_at_rejected(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(201, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    with pytest.raises(PlanRejected, match="not newer"):
        await driver.run_cycle({}, last_generated_at="2026-07-05T12:00:05Z")


@respx.mock
async def test_emhass_down_raises_httpx(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").mock(
        side_effect=httpx.ConnectError("down")
    )
    with pytest.raises(httpx.HTTPError):
        await driver.run_cycle({})


@respx.mock
async def test_healthz(driver):
    respx.get(f"{BASE}/healthz").respond(200, json={"status": "ok"})
    assert await driver.healthy() is True
    respx.get(f"{BASE}/healthz").mock(side_effect=httpx.ConnectError("down"))
    assert await driver.healthy() is False
