"""main.py wiring that is testable without a broker or a server."""

import inspect

import pytest

from flexd.main import mqtt_loop


class Stop(BaseException):
    """Raised by the fake factory to end the otherwise endless loop; a BaseException
    so the loop's catch-all (the behaviour under test) does not swallow it."""


async def test_mqtt_loop_survives_any_exception_and_reconnects():
    # #1 Lows: only MqttError was caught; anything else cancelled the gathered REST
    # server and scheduler with it
    attempts, sleeps = [], []

    def factory(*a, **kw):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("tls handshake exploded")
        raise Stop()

    async def fake_sleep(s):
        sleeps.append(s)

    holder = {"bridge": object()}
    with pytest.raises(Stop):
        await mqtt_loop(
            host="broker",
            port=1883,
            username=None,
            password=None,
            base_topic="flexd",
            make_bridge=lambda client: object(),
            bridge_holder=holder,
            client_factory=factory,
            retry_s=10.0,
            sleep=fake_sleep,
        )
    assert len(attempts) == 2
    assert sleeps == [10.0]
    assert holder["bridge"] is None  # publishers see "no broker" while reconnecting


def test_mqtt_loop_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(mqtt_loop)
