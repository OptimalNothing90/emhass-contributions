from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from flexd.models import Demand


def _base(**kw):
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
    return d


def test_minimal_demand_defaults():
    d = Demand(**_base())
    assert d.type == "generic"
    assert d.flexibility == "shiftable"
    assert d.interruptible is True
    assert d.priority == 1
    assert d.p_min_w == 0
    assert d.current_power_w == 0
    assert d.ttl_s > 0  # derived from expires_at - created_at


def test_id_pattern_rejected():
    with pytest.raises(ValidationError):
        Demand(**_base(id="../evil"))
    with pytest.raises(ValidationError):
        Demand(**_base(id="UPPER"))


def test_expires_at_mandatory():
    bad = _base()
    del bad["expires_at"]
    with pytest.raises(ValidationError):
        Demand(**bad)


def test_naive_datetimes_rejected():
    with pytest.raises(ValidationError):
        Demand(**_base(deadline=datetime(2026, 7, 6, 5, 0)))  # no tzinfo


def test_datetimes_normalized_to_utc():
    cet = timezone(timedelta(hours=2))
    d = Demand(**_base(deadline=datetime(2026, 7, 6, 5, 0, tzinfo=cet)))
    assert d.deadline.tzinfo == timezone.utc
    assert d.deadline.hour == 3
