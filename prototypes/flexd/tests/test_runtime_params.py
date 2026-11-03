"""Runtime-params provider: a JSON document with `generated_at`, read on every solve."""

from datetime import timedelta

import httpx
import pytest
import respx

from flexd.runtime_params import StaleInputs
from tests.conftest import (
    PROVIDER_DOC,
    PROVIDER_GENERATED_AT as T0,
    file_provider,
    url_provider,
    write_provider_doc,
)

URL = "http://relay.local:8080/runtime-params.json"


# -- file ---------------------------------------------------------------------


async def test_file_provider_returns_params_without_generated_at(tmp_path):
    params = await file_provider(write_provider_doc(tmp_path)).fetch(
        now=T0 + timedelta(seconds=90)
    )
    assert "generated_at" not in params
    assert params["soc_init"] == 0.62
    assert len(params["pv_power_forecast"]) == 12


async def test_file_exactly_max_age_old_is_still_fresh(tmp_path):
    params = await file_provider(write_provider_doc(tmp_path)).fetch(
        now=T0 + timedelta(seconds=600)
    )
    assert params["soc_init"] == 0.62


async def test_file_one_second_past_max_age_is_stale(tmp_path):
    with pytest.raises(StaleInputs, match="601"):
        await file_provider(write_provider_doc(tmp_path)).fetch(
            now=T0 + timedelta(seconds=601)
        )


async def test_missing_generated_at_is_stale(tmp_path):
    provider = file_provider(write_provider_doc(tmp_path, generated_at=None))
    with pytest.raises(StaleInputs, match="generated_at"):
        await provider.fetch(now=T0)


async def test_generated_at_without_offset_is_stale(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2026-07-05T11:58:30")
    )
    with pytest.raises(StaleInputs, match="timezone"):
        await provider.fetch(now=T0)


async def test_generated_at_with_z_suffix_is_accepted(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2026-07-05T11:58:30Z")
    )
    params = await provider.fetch(now=T0 + timedelta(seconds=10))
    assert "generated_at" not in params


async def test_missing_file_is_stale(tmp_path):
    with pytest.raises(StaleInputs, match="nope.json"):
        await file_provider(tmp_path / "nope.json").fetch(now=T0)


async def test_unparsable_file_is_stale(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(now=T0)


async def test_non_object_document_is_stale(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(StaleInputs, match="object"):
        await file_provider(p).fetch(now=T0)


# -- url ----------------------------------------------------------------------


@respx.mock
async def test_url_provider_returns_params():
    respx.get(URL).respond(200, json=PROVIDER_DOC)
    params = await url_provider(URL).fetch(now=T0 + timedelta(seconds=30))
    assert params["soc_init"] == 0.62
    assert "generated_at" not in params


@respx.mock
async def test_url_provider_stale_document_is_stale():
    respx.get(URL).respond(200, json=PROVIDER_DOC)
    with pytest.raises(StaleInputs):
        await url_provider(URL).fetch(now=T0 + timedelta(hours=1))


@respx.mock
async def test_url_http_error_is_stale():
    respx.get(URL).respond(503, text="relay restarting")
    with pytest.raises(StaleInputs, match="503"):
        await url_provider(URL).fetch(now=T0)


@respx.mock
async def test_url_unreachable_is_stale():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(StaleInputs, match="unreachable"):
        await url_provider(URL).fetch(now=T0)


@respx.mock
async def test_url_unparsable_body_is_stale():
    respx.get(URL).respond(200, text="<html>oops</html>")
    with pytest.raises(StaleInputs, match="JSON"):
        await url_provider(URL).fetch(now=T0)


# -- review round: failure modes that must read as stale, not crash the cycle --


async def test_future_generated_at_beyond_max_age_is_stale(tmp_path):
    # a relay clock far ahead must not produce a document that never ages out
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2030-01-01T00:00:00+00:00")
    )
    with pytest.raises(StaleInputs, match="future"):
        await provider.fetch(now=T0)


async def test_future_generated_at_within_max_age_is_fresh(tmp_path):
    # small clock skew between relay and flexd is tolerated
    provider = file_provider(
        write_provider_doc(
            tmp_path, generated_at=(T0 + timedelta(seconds=30)).isoformat()
        )
    )
    assert "soc_init" in await provider.fetch(now=T0)


async def test_non_utf8_file_is_stale(tmp_path):
    p = tmp_path / "utf16.json"
    p.write_bytes('{"generated_at": "x"}'.encode("utf-16"))
    with pytest.raises(StaleInputs, match="unreadable"):
        await file_provider(p).fetch(now=T0)


async def test_malformed_url_is_stale():
    with pytest.raises(StaleInputs, match="unreachable"):
        await url_provider("relay:8080/params.json").fetch(now=T0)


# -- Codex review round: bounded fetch, bounded document, strict JSON --


@respx.mock
async def test_url_trickling_response_times_out_as_stale(monkeypatch):
    import asyncio

    from flexd import runtime_params

    monkeypatch.setattr(runtime_params, "FETCH_TIMEOUT_S", 0.05)

    async def slow(request):
        await asyncio.sleep(0.5)
        return httpx.Response(200, json=PROVIDER_DOC)

    respx.get(URL).mock(side_effect=slow)
    with pytest.raises(StaleInputs, match="timed out"):
        await url_provider(URL).fetch(now=T0)


async def test_oversized_file_is_stale(tmp_path):
    from flexd import runtime_params

    p = tmp_path / "big.json"
    p.write_text(
        '{"generated_at": "2026-07-05T11:58:30+00:00", "pad": "'
        + "x" * (runtime_params.MAX_DOC_BYTES + 1)
        + '"}',
        encoding="utf-8",
    )
    with pytest.raises(StaleInputs, match="too large"):
        await file_provider(p).fetch(now=T0)


@respx.mock
async def test_oversized_url_body_is_stale():
    from flexd import runtime_params

    respx.get(URL).respond(200, text="x" * (runtime_params.MAX_DOC_BYTES + 1))
    with pytest.raises(StaleInputs, match="too large"):
        await url_provider(URL).fetch(now=T0)


async def test_nan_in_document_is_stale(tmp_path):
    p = tmp_path / "nan.json"
    p.write_text(
        '{"generated_at": "2026-07-05T11:58:30+00:00", "soc_init": NaN}',
        encoding="utf-8",
    )
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(now=T0)


async def test_deeply_nested_document_is_stale(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(now=T0)
