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


def test_explicit_ttl_passthrough():
    d = Demand(**_base(ttl_s=3600))
    assert d.ttl_s == 3600


def test_negative_ttl_rejected():
    with pytest.raises(ValidationError):
        Demand(**_base(ttl_s=-1))


def test_window_start_after_deadline_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Demand(**_base(window_start=now + timedelta(hours=10)))


def test_p_min_above_nominal_rejected():
    with pytest.raises(ValidationError):
        Demand(**_base(p_min_w=3000))
