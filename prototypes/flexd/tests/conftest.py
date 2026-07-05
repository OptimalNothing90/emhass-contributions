from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from flexd.models import Demand
from flexd.registry import Registry


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
