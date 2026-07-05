"""Entry point: load config, wire modules, run REST + MQTT + scheduler concurrently.

MQTT is optional: if the broker is unreachable, REST and the cycle keep running;
the bridge reconnects with backoff. Config errors render as clean one-line exits
(SystemExit from load_config for file problems; ValidationError/ValueError for
content problems are caught here and re-rendered).
"""

import asyncio
import logging
import os
from datetime import timedelta

import aiomqtt
import uvicorn
from pydantic import ValidationError

from flexd.config import load_config
from flexd.emhass_driver import EmhassDriver
from flexd.plan_view import PlanView
from flexd.registry import Registry
from flexd.scheduler import Scheduler
from flexd.standing import StandingManager
from flexd.templates import TemplateManager
from flexd.transports.mqtt_bridge import MqttBridge
from flexd.transports.rest_api import create_app

log = logging.getLogger("flexd")

KNOWN_SCHEMA_VERSIONS = {"1.0"}


async def run() -> None:
    logging.basicConfig(level=os.environ.get("FLEXD_LOG_LEVEL", "INFO"))
    try:
        cfg = load_config(os.environ.get("FLEXD_CONFIG", "/config/flexd.yaml"))
    except (ValidationError, ValueError) as exc:
        raise SystemExit(f"flexd: invalid configuration: {exc}")
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    registry = Registry(cfg.data_dir / "demands.json")
    view = PlanView(
        cfg.data_dir / "adopted_plan.json",
        stale_after=timedelta(minutes=cfg.timestep_min * cfg.stale_after_cycles),
    )
    driver = EmhassDriver(cfg.emhass_url, known_schema_versions=KNOWN_SCHEMA_VERSIONS)
    standing = StandingManager(
        cfg.standing_demands,
        ledger_path=cfg.data_dir / "standing_ledger.json",
        tz=cfg.timezone,
        registry=registry,
    )
    templates = TemplateManager(
        cfg.templates,
        tz=cfg.timezone,
        registry=registry,
        default_ttl_s=cfg.default_ttl_s,
    )

    bridge_holder: dict = {"bridge": None}

    async def on_cycle_end(state: str, swept_ids: list[str]) -> None:
        bridge = bridge_holder["bridge"]
        if bridge is None:
            if swept_ids:
                # no broker right now: fail the delivery so the scheduler keeps the
                # swept ids for redelivery — otherwise their retained topics ghost forever
                raise RuntimeError(
                    "mqtt bridge unavailable; swept ids kept for redelivery"
                )
            return
        await bridge.clear_expired(swept_ids)  # spec: no ghost retained setpoints
        await bridge.publish_plan(state=state)

    scheduler = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=standing,
        timestep_min=cfg.timestep_min,
        horizon_steps=cfg.horizon_steps,
        extra_runtime_params=cfg.extra_runtime_params,
        crumb_path=cfg.data_dir / "last_cycle.json",
        on_cycle_end=on_cycle_end,
    )
    scheduler.bind_loop(
        asyncio.get_running_loop()
    )  # before REST serves: threadsafe notify_change

    app = create_app(
        registry=registry,
        view=view,
        scheduler=scheduler,
        driver=driver,
        standing=standing,
        templates=templates,
        default_ttl_s=cfg.default_ttl_s,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",
            port=int(os.environ.get("FLEXD_PORT", "8321")),
            log_level="info",
        )
    )

    async def mqtt_loop() -> None:
        if not cfg.mqtt.enabled:
            return
        will = aiomqtt.Will(
            f"{cfg.mqtt.base_topic}/availability", "offline", retain=True
        )
        while True:
            try:
                async with aiomqtt.Client(
                    cfg.mqtt.host,
                    cfg.mqtt.port,
                    username=cfg.mqtt.username,
                    password=cfg.mqtt.password,
                    will=will,
                ) as client:
                    bridge = MqttBridge(
                        client=client,
                        base_topic=cfg.mqtt.base_topic,
                        registry=registry,
                        view=view,
                        scheduler=scheduler,
                        standing=standing,
                        templates=templates,
                    )
                    bridge_holder["bridge"] = bridge
                    await client.publish(
                        f"{cfg.mqtt.base_topic}/availability", "online", retain=True
                    )
                    await client.subscribe(f"{cfg.mqtt.base_topic}/demands/+/+/set")
                    await client.subscribe(f"{cfg.mqtt.base_topic}/demands/+/+/delete")
                    await client.subscribe(f"{cfg.mqtt.base_topic}/templates/+/+/start")
                    async for message in client.messages:
                        try:
                            await bridge.handle_message(
                                str(message.topic),
                                message.payload.decode("utf-8", "replace"),
                            )
                        except Exception:
                            log.exception("mqtt message handling failed; continuing")
            except aiomqtt.MqttError as exc:
                bridge_holder["bridge"] = None
                log.warning("mqtt disconnected (%s); retrying in 10s", exc)
                await asyncio.sleep(10)

    await asyncio.gather(server.serve(), scheduler.run_forever(), mqtt_loop())


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    cli()
