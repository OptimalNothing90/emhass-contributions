import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from flexd.emhass_driver import FIRST_BOOT_SLACK, EmhassDriver, PlanRejected

FIX = Path(__file__).parent / "fixtures"
BASE = "http://emhass:5000"


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture
def driver():
    return EmhassDriver(BASE, known_schema_versions={"1.0"})


@respx.mock
async def test_run_cycle_ok(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    plan = await driver.run_cycle({"prediction_horizon": 48})
    assert plan["status"] == "ok"
    assert len(plan["plan"]) == 2


@respx.mock
async def test_no_run_raises(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_no_run.json"))
    with pytest.raises(PlanRejected, match="no-run"):
        await driver.run_cycle({})


@respx.mock
async def test_unknown_schema_rejected(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_bad_schema.json"))
    with pytest.raises(PlanRejected, match="schema"):
        await driver.run_cycle({})


@respx.mock
async def test_stale_generated_at_rejected(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    with pytest.raises(PlanRejected, match="not newer"):
        await driver.run_cycle({}, last_generated_at="2026-07-05T12:00:05Z")


@respx.mock
async def test_ok_without_generated_at_rejected(driver):
    bad = fixture("plan_ok.json")
    bad["generated_at"] = None
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=bad)
    with pytest.raises(PlanRejected, match="generated_at"):
        await driver.run_cycle({})


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


# -- #1 Medium 7: first boot must not adopt an arbitrarily old re-served plan --
@respx.mock
async def test_first_boot_rejects_plan_older_than_one_cycle(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    two_days_later = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(PlanRejected, match="older than"):
        await driver.run_cycle(
            {}, last_generated_at=None, now=two_days_later, timestep_min=30
        )


@respx.mock
async def test_first_boot_accepts_plan_generated_this_cycle(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    now = datetime(2026, 7, 5, 12, 10, tzinfo=timezone.utc)  # 10 min after generated_at
    plan = await driver.run_cycle({}, last_generated_at=None, now=now, timestep_min=30)
    assert plan["status"] == "ok"


@respx.mock
async def test_first_boot_tolerance_is_one_cycle_plus_slack(driver):
    respx.post(f"{BASE}/action/naive-mpc-optim").respond(200, text="ok")
    respx.get(f"{BASE}/api/v1/plan").respond(200, json=fixture("plan_ok.json"))
    gen = datetime(2026, 7, 5, 12, 0, 5, tzinfo=timezone.utc)
    within = gen + timedelta(minutes=30) + FIRST_BOOT_SLACK - timedelta(seconds=1)
    beyond = gen + timedelta(minutes=30) + FIRST_BOOT_SLACK + timedelta(seconds=1)
    await driver.run_cycle({}, now=within, timestep_min=30)
    with pytest.raises(PlanRejected, match="older than"):
        await driver.run_cycle({}, now=beyond, timestep_min=30)
