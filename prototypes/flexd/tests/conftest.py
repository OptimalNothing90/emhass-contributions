from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flexd.models import Demand
from flexd.registry import Registry
from flexd.transports.rest_api import create_app

NOW_REAL = datetime.now(timezone.utc)


def make_demand(**kw) -> Demand:
    now = datetime.now(timezone.utc)
    d = dict(
        id="dishwasher",
        source="loxone",
        energy_target_wh=1200,
        nominal_power_w=2000,
        deadline=now + timedelta(hours=8),
        expires_at=now + timedelta(hours=9),
    )
    d.update(kw)
    return Demand(**d)


@pytest.fixture
def registry(tmp_path: Path) -> Registry:
    return Registry(tmp_path / "demands.json")


class FakeStandingRegistry:
    def is_standing(self, demand_id):
        return demand_id == "waterheater"


@pytest.fixture
def client(registry):
    # deferred import: test_scheduler imports make_demand from this module,
    # so importing it at module scope here would create a circular import
    from tests.test_scheduler import PLAN, FakeDriver, FakeView, make_scheduler

    view = FakeView()
    scheduler = make_scheduler(registry, FakeDriver(result=PLAN), view)
    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=FakeDriver(result=PLAN),
        standing=FakeStandingRegistry(),
    )
    return TestClient(app)


def _payload(**kw):
    d = dict(
        id="dishwasher",
        source="loxone",
        energy_target_wh=1200,
        nominal_power_w=2000,
        deadline=(NOW_REAL + timedelta(hours=8)).isoformat(),
        expires_at=(NOW_REAL + timedelta(hours=9)).isoformat(),
    )
    d.update(kw)
    return d
