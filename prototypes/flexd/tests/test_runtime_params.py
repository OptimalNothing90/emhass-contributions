"""Runtime-params provider: a JSON document with `generated_at`, read on every solve."""

from datetime import timedelta

import httpx
import pytest
import respx

from flexd.runtime_params import StaleInputs
from tests.conftest import (
    PROVIDER_DOC,
    PROVIDER_FIRST_STEP as STEP0,
    PROVIDER_GENERATED_AT as T0,
    file_provider,
    url_provider,
    write_provider_doc,
)

URL = "http://relay.local:8080/runtime-params.json"


# -- file ---------------------------------------------------------------------


async def test_file_provider_returns_params_without_generated_at(tmp_path):
    params = await file_provider(write_provider_doc(tmp_path)).fetch(
        first_step_start=STEP0, now=T0 + timedelta(seconds=90)
    )
    assert "generated_at" not in params
    assert "first_step_start" not in params  # consumed, not forwarded to EMHASS
    assert params["soc_init"] == 0.62
    assert len(params["pv_power_forecast"]) == 48


async def test_file_exactly_max_age_old_is_still_fresh(tmp_path):
    params = await file_provider(write_provider_doc(tmp_path)).fetch(
        first_step_start=STEP0, now=T0 + timedelta(seconds=600)
    )
    assert params["soc_init"] == 0.62


async def test_file_one_second_past_max_age_is_stale(tmp_path):
    with pytest.raises(StaleInputs, match="601"):
        await file_provider(write_provider_doc(tmp_path)).fetch(
            first_step_start=STEP0, now=T0 + timedelta(seconds=601)
        )


async def test_missing_generated_at_is_stale(tmp_path):
    provider = file_provider(write_provider_doc(tmp_path, generated_at=None))
    with pytest.raises(StaleInputs, match="generated_at"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_generated_at_without_offset_is_stale(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2026-07-05T11:58:30")
    )
    with pytest.raises(StaleInputs, match="timezone"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_generated_at_with_z_suffix_is_accepted(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2026-07-05T11:58:30Z")
    )
    params = await provider.fetch(
        first_step_start=STEP0, now=T0 + timedelta(seconds=10)
    )
    assert "generated_at" not in params


async def test_missing_file_is_stale(tmp_path):
    with pytest.raises(StaleInputs, match="nope.json"):
        await file_provider(tmp_path / "nope.json").fetch(
            first_step_start=STEP0, now=T0
        )


async def test_unparsable_file_is_stale(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


async def test_non_object_document_is_stale(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(StaleInputs, match="object"):
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


# -- url ----------------------------------------------------------------------


@respx.mock
async def test_url_provider_returns_params():
    respx.get(URL).respond(200, json=PROVIDER_DOC)
    params = await url_provider(URL).fetch(
        first_step_start=STEP0, now=T0 + timedelta(seconds=30)
    )
    assert params["soc_init"] == 0.62
    assert "generated_at" not in params


@respx.mock
async def test_url_provider_stale_document_is_stale():
    respx.get(URL).respond(200, json=PROVIDER_DOC)
    with pytest.raises(StaleInputs):
        await url_provider(URL).fetch(
            first_step_start=STEP0, now=T0 + timedelta(hours=1)
        )


@respx.mock
async def test_url_http_error_is_stale():
    respx.get(URL).respond(503, text="relay restarting")
    with pytest.raises(StaleInputs, match="503"):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


@respx.mock
async def test_url_unreachable_is_stale():
    respx.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(StaleInputs, match="unreachable"):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


@respx.mock
async def test_url_unparsable_body_is_stale():
    respx.get(URL).respond(200, text="<html>oops</html>")
    with pytest.raises(StaleInputs, match="JSON"):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


# -- review round: failure modes that must read as stale, not crash the cycle --


async def test_future_generated_at_beyond_max_age_is_stale(tmp_path):
    # a relay clock far ahead must not produce a document that never ages out
    provider = file_provider(
        write_provider_doc(tmp_path, generated_at="2030-01-01T00:00:00+00:00")
    )
    with pytest.raises(StaleInputs, match="future"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_future_generated_at_within_max_age_is_fresh(tmp_path):
    # small clock skew between relay and flexd is tolerated
    provider = file_provider(
        write_provider_doc(
            tmp_path, generated_at=(T0 + timedelta(seconds=30)).isoformat()
        )
    )
    assert "soc_init" in await provider.fetch(first_step_start=STEP0, now=T0)


async def test_non_utf8_file_is_stale(tmp_path):
    p = tmp_path / "utf16.json"
    p.write_bytes('{"generated_at": "x"}'.encode("utf-16"))
    with pytest.raises(StaleInputs, match="unreadable"):
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


async def test_malformed_url_is_stale():
    with pytest.raises(StaleInputs, match="unreachable"):
        await url_provider("relay:8080/params.json").fetch(
            first_step_start=STEP0, now=T0
        )


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
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


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
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


@respx.mock
async def test_oversized_url_body_is_stale():
    from flexd import runtime_params

    respx.get(URL).respond(200, text="x" * (runtime_params.MAX_DOC_BYTES + 1))
    with pytest.raises(StaleInputs, match="too large"):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


async def test_nan_in_document_is_stale(tmp_path):
    p = tmp_path / "nan.json"
    p.write_text(
        '{"generated_at": "2026-07-05T11:58:30+00:00", "soc_init": NaN}',
        encoding="utf-8",
    )
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


async def test_deeply_nested_document_is_stale(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(StaleInputs, match="JSON"):
        await file_provider(p).fetch(first_step_start=STEP0, now=T0)


# -- LesIT1 asks (issue #1, 2026-11-04): step stamp, list lengths, readable reason --


async def test_first_step_start_one_step_off_is_stale(tmp_path):
    # mid-slot re-solve (module docstring): fresh by age, built for 12:00, solve at 12:30
    provider = file_provider(write_provider_doc(tmp_path), max_age_s=1800)
    with pytest.raises(StaleInputs, match="12:00:00.*12:30:00") as info:
        await provider.fetch(
            first_step_start=STEP0 + timedelta(minutes=30),
            now=T0 + timedelta(minutes=20),
        )
    assert "first_step_start" in str(info.value)


@pytest.mark.parametrize(
    "stamp",
    ["2026-07-05T14:00:00+02:00", "2026-07-05T12:00:00.000000Z", "2026-07-05T12:00Z"],
)
async def test_first_step_start_compares_as_an_instant(tmp_path, stamp):
    provider = file_provider(write_provider_doc(tmp_path, first_step_start=stamp))
    params = await provider.fetch(first_step_start=STEP0, now=T0)
    assert params["soc_init"] == 0.62


async def test_first_step_start_without_offset_is_stale(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, first_step_start="2026-07-05T12:00:00")
    )
    with pytest.raises(StaleInputs, match="first_step_start.*timezone"):
        await provider.fetch(first_step_start=STEP0, now=T0)


@pytest.mark.parametrize("value", [12, "", "x" * 65])
async def test_first_step_start_that_is_not_a_short_string_is_stale(tmp_path, value):
    provider = file_provider(write_provider_doc(tmp_path, first_step_start=value))
    with pytest.raises(StaleInputs, match="first_step_start must be") as info:
        await provider.fetch(first_step_start=STEP0, now=T0)
    assert "x" * 65 not in str(info.value)  # never echoed unbounded


async def test_document_without_first_step_start_passes_on_age_alone(tmp_path):
    # backwards compatible: a relay that does not stamp the step is checked by age only
    provider = file_provider(write_provider_doc(tmp_path, first_step_start=None))
    params = await provider.fetch(
        first_step_start=STEP0 + timedelta(hours=3), now=T0 + timedelta(minutes=5)
    )
    assert params["soc_init"] == 0.62


async def test_list_shorter_than_the_horizon_is_stale(tmp_path):
    provider = file_provider(write_provider_doc(tmp_path, pv_power_forecast=[0] * 12))
    with pytest.raises(StaleInputs, match="pv_power_forecast.*12.*48"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_list_longer_than_the_horizon_is_stale(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, load_cost_forecast=[0.2] * 49)
    )
    with pytest.raises(StaleInputs, match="load_cost_forecast.*49.*48"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_list_length_is_checked_against_the_configured_horizon(tmp_path):
    provider = file_provider(write_provider_doc(tmp_path), horizon_steps=12)
    with pytest.raises(StaleInputs, match="48.*12"):
        await provider.fetch(first_step_start=STEP0, now=T0)


async def test_lists_flexd_overrides_anyway_are_not_length_checked(tmp_path):
    # the aggregator drops these with a warning; a wrong length there is not stale data
    provider = file_provider(
        write_provider_doc(
            tmp_path, def_total_hours=[9], nominal_power_of_deferrable_loads=[1, 2]
        )
    )
    params = await provider.fetch(first_step_start=STEP0, now=T0)
    assert params["def_total_hours"] == [9]


async def test_scalars_and_nested_lists_are_not_length_checked(tmp_path):
    provider = file_provider(
        write_provider_doc(tmp_path, soc_init=0.5, weather_forecast_cache={"a": [1]})
    )
    params = await provider.fetch(first_step_start=STEP0, now=T0)
    assert params["weather_forecast_cache"] == {"a": [1]}


@respx.mock
async def test_url_http_error_carries_the_response_body():
    respx.get(URL).respond(503, text="bridge: evcc unreachable, no forecast")
    with pytest.raises(StaleInputs, match="HTTP 503.*evcc unreachable"):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"k" * 5000: []},  # key echoed by the length check
        {"generated_at": "2026-07-05T" + "9" * 5000},  # value echoed by the parser
    ],
    ids=["long-key", "long-generated_at"],
)
async def test_reason_text_is_bounded_on_every_path(tmp_path, overrides):
    # the text goes to a retained MQTT payload and last_cycle.json: never unbounded
    from flexd.runtime_params import MAX_REASON_CHARS

    provider = file_provider(write_provider_doc(tmp_path, **overrides))
    with pytest.raises(StaleInputs) as info:
        await provider.fetch(first_step_start=STEP0, now=T0)
    assert len(str(info.value)) <= MAX_REASON_CHARS
    assert str(info.value).startswith(str(tmp_path))


@respx.mock
@pytest.mark.parametrize(
    ("body", "expected"),
    [("x" * 2000, r"HTTP 503: x{500}$"), ("", r"HTTP 503$")],
    ids=["bounded", "no-body"],
)
async def test_url_http_error_body_is_bounded(body, expected):
    respx.get(URL).respond(503, text=body)
    with pytest.raises(StaleInputs, match=expected):
        await url_provider(URL).fetch(first_step_start=STEP0, now=T0)
