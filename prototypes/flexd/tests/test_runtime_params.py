"""Runtime-params provider: a JSON document with `generated_at`, read on every solve."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from flexd.runtime_params import RuntimeParamsProvider, StaleInputs

FIXTURE = Path(__file__).parent / "fixtures" / "runtime_params_provider.json"
GENERATED_AT = datetime(2026, 7, 5, 11, 58, 30, tzinfo=timezone.utc)
URL = "http://relay.local:8080/runtime-params.json"


def write_doc(tmp_path: Path, **overrides) -> Path:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc.update(overrides)
    for key, value in list(doc.items()):
        if value is None:
            del doc[key]
    p = tmp_path / "runtime-params.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


# -- file ---------------------------------------------------------------------


async def test_file_provider_returns_params_without_generated_at():
    provider = RuntimeParamsProvider(path=FIXTURE, max_age_s=600)
    params = await provider.fetch(now=GENERATED_AT + timedelta(seconds=90))
    assert "generated_at" not in params
    assert params["soc_init"] == 0.62
    assert len(params["pv_power_forecast"]) == 12


async def test_file_exactly_max_age_old_is_still_fresh():
    provider = RuntimeParamsProvider(path=FIXTURE, max_age_s=600)
    params = await provider.fetch(now=GENERATED_AT + timedelta(seconds=600))
    assert params["soc_init"] == 0.62


async def test_file_one_second_past_max_age_is_stale():
    provider = RuntimeParamsProvider(path=FIXTURE, max_age_s=600)
    with pytest.raises(StaleInputs, match="601"):
        await provider.fetch(now=GENERATED_AT + timedelta(seconds=601))


async def test_missing_generated_at_is_stale(tmp_path):
    p = write_doc(tmp_path, generated_at=None)
    provider = RuntimeParamsProvider(path=p, max_age_s=600)
    with pytest.raises(StaleInputs, match="generated_at"):
        await provider.fetch(now=GENERATED_AT)


async def test_generated_at_without_offset_is_stale(tmp_path):
    p = write_doc(tmp_path, generated_at="2026-07-05T11:58:30")
    provider = RuntimeParamsProvider(path=p, max_age_s=600)
    with pytest.raises(StaleInputs, match="offset"):
        await provider.fetch(now=GENERATED_AT)


async def test_generated_at_with_z_suffix_is_accepted(tmp_path):
    p = write_doc(tmp_path, generated_at="2026-07-05T11:58:30Z")
    provider = RuntimeParamsProvider(path=p, max_age_s=600)
    params = await provider.fetch(now=GENERATED_AT + timedelta(seconds=10))
    assert params["soc_init"] == 0.62


async def test_missing_file_is_stale(tmp_path):
    provider = RuntimeParamsProvider(path=tmp_path / "nope.json", max_age_s=600)
    with pytest.raises(StaleInputs, match="nope.json"):
        await provider.fetch(now=GENERATED_AT)


async def test_unparsable_file_is_stale(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    provider = RuntimeParamsProvider(path=p, max_age_s=600)
    with pytest.raises(StaleInputs, match="JSON"):
        await provider.fetch(now=GENERATED_AT)


async def test_non_object_document_is_stale(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    provider = RuntimeParamsProvider(path=p, max_age_s=600)
    with pytest.raises(StaleInputs, match="object"):
        await provider.fetch(now=GENERATED_AT)


# -- url ----------------------------------------------------------------------


@respx.mock
async def test_url_provider_returns_params():
    respx.get(URL).respond(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))
    provider = RuntimeParamsProvider(url=URL, max_age_s=600)
    params = await provider.fetch(now=GENERATED_AT + timedelta(seconds=30))
    assert params["soc_init"] == 0.62
    assert "generated_at" not in params


@respx.mock
async def test_url_provider_stale_document_is_stale():
    respx.get(URL).respond(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))
    provider = RuntimeParamsProvider(url=URL, max_age_s=600)
    with pytest.raises(StaleInputs):
        await provider.fetch(now=GENERATED_AT + timedelta(hours=1))


@respx.mock
async def test_url_http_error_is_stale():
    respx.get(URL).respond(503, text="relay restarting")
    provider = RuntimeParamsProvider(url=URL, max_age_s=600)
    with pytest.raises(StaleInputs, match="503"):
        await provider.fetch(now=GENERATED_AT)


@respx.mock
async def test_url_unreachable_is_stale():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    provider = RuntimeParamsProvider(url=URL, max_age_s=600)
    with pytest.raises(StaleInputs, match="unreachable"):
        await provider.fetch(now=GENERATED_AT)


@respx.mock
async def test_url_unparsable_body_is_stale():
    respx.get(URL).respond(200, text="<html>oops</html>")
    provider = RuntimeParamsProvider(url=URL, max_age_s=600)
    with pytest.raises(StaleInputs, match="JSON"):
        await provider.fetch(now=GENERATED_AT)


def test_provider_requires_exactly_one_source():
    with pytest.raises(ValueError):
        RuntimeParamsProvider(max_age_s=600)
    with pytest.raises(ValueError):
        RuntimeParamsProvider(path=FIXTURE, url=URL, max_age_s=600)
