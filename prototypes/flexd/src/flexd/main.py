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
from flexd.pending_clear import PendingClear
from flexd.plan_view import PlanView
from flexd.registry import Registry
from flexd.scheduler import Scheduler
from flexd.standing import StandingManager
from flexd.templates import TemplateManager
from flexd.transports.mqtt_bridge import MqttBridge
from flexd.transports.rest_api import create_app

log = logging.getLogger("flexd")

KNOWN_SCHEMA_VERSIONS = {"1.0"}
MQTT_RETRY_S = 10.0


async def mqtt_loop(
    *,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    base_topic: str,
    make_bridge,
    bridge_holder: dict,
    client_factory=aiomqtt.Client,
    retry_s: float = MQTT_RETRY_S,
    sleep=asyncio.sleep,
) -> None:
    """Connect, subscribe, dispatch; on ANY failure drop the bridge, log and reconnect.

    Only MqttError used to be caught, and with an unqualified asyncio.gather any other
    exception from the MQTT side cancelled the REST server and the scheduler with it
    (#1 Lows). Cancellation still propagates.
    """
    will = aiomqtt.Will(f"{base_topic}/availability", "offline", retain=True)
    while True:
        try:
            async with client_factory(
                host, port, username=username, password=password, will=will
            ) as client:
                bridge_holder["bridge"] = make_bridge(client)
                await client.publish(
                    f"{base_topic}/availability", "online", retain=True
                )
                await client.subscribe(f"{base_topic}/demands/+/+/set")
                await client.subscribe(f"{base_topic}/demands/+/+/delete")
                await client.subscribe(f"{base_topic}/demands/+/+/refresh")
                await client.subscribe(f"{base_topic}/templates/+/+/start")
                async for message in client.messages:
                    try:
                        await bridge_holder["bridge"].handle_message(
                            str(message.topic),
                            message.payload.decode("utf-8", "replace"),
                        )
                    except Exception:
                        log.exception("mqtt message handling failed; continuing")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — the loop must outlive any broker/client fault
            bridge_holder["bridge"] = None
            log.warning(
                "mqtt loop failed (%s: %s); retrying in %ss",
                type(exc).__name__,
                exc,
                retry_s,
            )
            await sleep(retry_s)


async def run() -> None:
    logging.basicConfig(level=os.environ.get("FLEXD_LOG_LEVEL", "INFO"))
    try:
        cfg = load_config(os.environ.get("FLEXD_CONFIG", "/config/flexd.yaml"))
    except (ValidationError, ValueError) as exc:
        raise SystemExit(f"flexd: invalid configuration: {exc}")
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    registry = Registry(
        cfg.data_dir / "demands.json",
        max_demands=cfg.max_demands,
        save_debounce_s=cfg.save_debounce_s,
        # survives a crash inside the debounce window (#1 Medium 11)
        pending_clear=PendingClear(cfg.data_dir / "pending_clear.json"),
    )
    standing_ids = {sd.id for sd in cfg.standing_demands}
    for d in registry.list_active():
        if d.id in standing_ids and d.source != "config":
            raise SystemExit(
                f"flexd: persisted demand {d.id!r} (source {d.source!r}) squats a standing id — "
                "remove it from demands.json or rename the standing demand"
            )
    view = PlanView(
        cfg.data_dir / "adopted_plan.json",
        stale_after=timedelta(minutes=cfg.timestep_min * cfg.stale_after_cycles),
        timestep=timedelta(minutes=cfg.timestep_min),
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

    async def _publish_off(demand_id: str) -> None:
        bridge = bridge_holder["bridge"]
        if bridge is None:
            raise RuntimeError(
                "mqtt bridge unavailable; cycle-end cleanup will cover it"
            )
        await bridge.publish_off(demand_id)

    scheduler = Scheduler(
        registry=registry,
        driver=driver,
        view=view,
        standing=standing,
        timestep_min=cfg.timestep_min,
        horizon_steps=cfg.horizon_steps,
        extra_runtime_params=cfg.extra_runtime_params,
        crumb_path=cfg.data_dir / "last_cycle.json",
        ts_round=cfg.ts_round,
        cycle_offset_s=cfg.cycle_offset_s,
        # without a broker there is nothing to deliver to — avoid a perpetual redelivery queue
        on_cycle_end=on_cycle_end if cfg.mqtt.enabled else None,
        on_demand_off=_publish_off if cfg.mqtt.enabled else None,
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

    def make_bridge(client) -> MqttBridge:
        return MqttBridge(
            client=client,
            base_topic=cfg.mqtt.base_topic,
            registry=registry,
            view=view,
            scheduler=scheduler,
            standing=standing,
            templates=templates,
        )

    tasks = [server.serve(), scheduler.run_forever()]
    if cfg.mqtt.enabled:
        tasks.append(
            mqtt_loop(
                host=cfg.mqtt.host,
                port=cfg.mqtt.port,
                username=cfg.mqtt.username,
                password=cfg.mqtt.password,
                base_topic=cfg.mqtt.base_topic,
                make_bridge=make_bridge,
                bridge_holder=bridge_holder,
            )
        )
    try:
        await asyncio.gather(*tasks)
    finally:
        registry.flush()  # a refresh still inside the debounce window must hit disk


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    cli()
