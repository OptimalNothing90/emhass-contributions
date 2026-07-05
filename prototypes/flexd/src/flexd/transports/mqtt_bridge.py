"""MQTT transport: demand intake + retained plan publish. Broker optional; REST never depends on this.

publish_plan/clear_expired are idempotent by construction (retained messages),
which the scheduler's at-least-once on_cycle_end delivery requires.
"""

import json
import logging

from fastapi import HTTPException

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError
from flexd.transports import reject_standing_squat

log = logging.getLogger(__name__)


class MqttBridge:
    def __init__(
        self,
        *,
        client,
        base_topic: str,
        registry,
        view,
        scheduler,
        standing=None,
        templates=None,
    ):
        self._client = client
        self._base = base_topic.rstrip("/")
        self._registry = registry
        self._view = view
        self._scheduler = scheduler
        self._standing = standing
        self._templates = templates  # wired in Task 12b

    # -- intake ---------------------------------------------------------------
    async def handle_message(self, topic: str, payload: str) -> None:
        parts = topic.split("/")
        # {base}/templates/{source}/{id}/start
        if len(parts) == 5 and parts[0] == self._base and parts[1] == "templates":
            _, _, source, template_id, action = parts
            if action != "start":
                log.debug("unknown action %r on %s", action, topic)
                return
            try:
                if self._templates is None:
                    raise KeyError(template_id)
                self._templates.start(template_id, source=source, now=utcnow())
                self._scheduler.notify_change()
            except (ValueError, KeyError, OwnershipError, HTTPException) as exc:
                detail = getattr(exc, "detail", None) or str(exc)
                await self._client.publish(
                    f"{self._base}/templates/{source}/{template_id}/error",
                    json.dumps({"error": detail}),
                    retain=False,
                )
            return
        # {base}/demands/{source}/{id}/{set|delete}
        if len(parts) != 5 or parts[0] != self._base or parts[1] != "demands":
            log.debug("ignoring non-intake topic %s", topic)
            return
        _, _, source, demand_id, action = parts
        try:
            if action == "set":
                reject_standing_squat(self._standing, demand_id, source)
                data = json.loads(payload)
                if not isinstance(data, dict):
                    raise ValueError("payload must be a JSON object")
                data.update({"id": demand_id, "source": source})
                self._registry.upsert(Demand(**data))
                self._scheduler.notify_change()
            elif action == "delete":
                if self._standing is not None and self._standing.is_standing(demand_id):
                    if source != "config":
                        raise OwnershipError(
                            f"{demand_id} is a standing demand; only source 'config' may mark it done"
                        )
                    self._standing.mark_done(demand_id, now=utcnow())
                else:
                    try:
                        self._registry.delete(demand_id, source=source)
                    except KeyError:
                        log.debug(
                            "delete for unknown %s ignored (idempotent redelivery)",
                            demand_id,
                        )
                await self._clear_demand_topics(demand_id)
                self._scheduler.notify_change()
            else:
                log.debug("unknown action %r on %s", action, topic)
        except (ValueError, KeyError, OwnershipError, HTTPException) as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            await self._client.publish(
                f"{self._base}/demands/{source}/{demand_id}/error",
                json.dumps({"error": detail}),
                retain=False,
            )

    # -- publish ----------------------------------------------------------------
    async def publish_plan(self, state: str) -> None:
        now = utcnow()
        await self._client.publish(
            f"{self._base}/plan/state",
            json.dumps({"state": state, "generated_at": self._view.generated_at}),
            retain=True,
        )
        for demand in self._registry.list_active(now=now):
            dv = self._view.demand_view(demand.id, now=now)
            setpoint = round(dv.setpoint_w) if dv else 0
            on = "1" if (dv and dv.on) else "0"
            await self._client.publish(
                f"{self._base}/plan/demands/{demand.id}/setpoint",
                str(setpoint),
                retain=True,
            )
            await self._client.publish(
                f"{self._base}/plan/demands/{demand.id}/on", on, retain=True
            )
        raw = self._view.raw_plan
        if raw is not None:
            await self._client.publish(
                f"{self._base}/plan/full", json.dumps(raw), retain=True
            )

    async def _clear_demand_topics(self, demand_id: str) -> None:
        for leaf in ("setpoint", "on"):
            await self._client.publish(
                f"{self._base}/plan/demands/{demand_id}/{leaf}", "", retain=True
            )

    async def clear_expired(self, expired_ids: list[str]) -> None:
        for demand_id in expired_ids:
            await self._clear_demand_topics(demand_id)
