"""MQTT transport: demand intake + retained plan publish. Broker optional; REST never depends on this.

publish_plan/clear_expired are idempotent by construction (retained messages),
which the scheduler's at-least-once on_cycle_end delivery requires.
"""

import json
import logging
from datetime import datetime

from fastapi import HTTPException

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError, RegistryFull
from flexd.templates import TemplateRunWithdrawn
from flexd.transports import live_demand_view, reject_standing_squat

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
        self._templates = templates  # template intake

    # -- intake ---------------------------------------------------------------
    async def handle_message(self, topic: str, payload: str) -> None:
        # Match by stripping the configured base, then split the remainder: a
        # multi-segment base such as home/flexd must work (#1 Medium 10).
        prefix = self._base + "/"
        if not topic.startswith(prefix):
            log.debug("ignoring non-intake topic %s", topic)
            return
        parts = topic[len(prefix) :].split("/")
        # {base}/templates/{source}/{id}/start
        if len(parts) == 4 and parts[0] == "templates":
            _, source, template_id, action = parts
            if action != "start":
                log.debug("unknown action %r on %s", action, topic)
                return
            try:
                if self._templates is None:
                    raise KeyError(template_id)
                self._templates.start(template_id, source=source, now=utcnow())
                self._scheduler.notify_change()
            except (
                ValueError,
                KeyError,
                OwnershipError,
                RegistryFull,
                TemplateRunWithdrawn,
                HTTPException,
            ) as exc:
                detail = getattr(exc, "detail", None) or str(exc)
                await self._client.publish(
                    f"{self._base}/templates/{source}/{template_id}/error",
                    json.dumps({"error": detail}),
                    retain=False,
                )
            return
        # {base}/demands/{source}/{id}/{set|delete|refresh}
        if len(parts) != 4 or parts[0] != "demands":
            log.debug("ignoring non-intake topic %s", topic)
            return
        _, source, demand_id, action = parts
        try:
            if action == "refresh":
                self._registry.refresh(demand_id, source=source)
            elif action == "set":
                data = json.loads(payload)
                if not isinstance(data, dict):
                    raise ValueError("payload must be a JSON object")
                if (
                    self._standing is not None
                    and self._standing.is_standing(demand_id)
                    and source == "config"
                ):
                    energy = data.get("energy_target_wh")
                    power = data.get("nominal_power_w")
                    if (
                        not isinstance(energy, (int, float))
                        or not isinstance(power, (int, float))
                        or power <= 0
                        or energy < 0
                    ):
                        raise ValueError(
                            "correction requires numeric energy_target_wh >= 0 and nominal_power_w > 0"
                        )
                    self._standing.correct(
                        demand_id,
                        remaining_hours=energy / power,
                        now=utcnow(),
                    )
                    self._scheduler.notify_change()
                    return
                reject_standing_squat(self._standing, demand_id, source)
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
                await self.publish_off(demand_id)  # explicit OFF before the clear
                await self._clear_demand_topics(demand_id)
                self._scheduler.notify_change()
            else:
                log.debug("unknown action %r on %s", action, topic)
        except (
            ValueError,
            KeyError,
            OwnershipError,
            RegistryFull,
            HTTPException,
        ) as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            await self._client.publish(
                f"{self._base}/demands/{source}/{demand_id}/error",
                json.dumps({"error": detail}),
                retain=False,
            )

    # -- publish ----------------------------------------------------------------
    async def publish_plan(self, state: str, now: datetime | None = None) -> None:
        now = now or utcnow()
        await self._client.publish(
            f"{self._base}/plan/state",
            json.dumps({"state": state, "generated_at": self._view.generated_at}),
            retain=True,
        )
        for demand in self._registry.list_active(now=now):
            # same gate as the HTTP reads: a demand registered after the adopted
            # plan was solved is pending (0), not the withdrawn run's slot
            dv, _ = live_demand_view(self._registry, self._view, demand.id, now=now)
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
        # ids the adopted plan still maps but the registry no longer holds as active
        # (expired during the solve, or withdrawn before this cycle's cleanup): OFF now
        active_ids = {d.id for d in self._registry.list_active(now=now)}
        for stale_id in self._view.mapped_ids() - active_ids:
            await self.publish_off(stale_id)
        raw = self._view.raw_plan
        if raw is not None:
            await self._client.publish(
                f"{self._base}/plan/full", json.dumps(raw), retain=True
            )

    async def publish_off(self, demand_id: str) -> None:
        """Explicit OFF (retained '0'): a consumer that keeps its last value must stop now.
        Clearing a retained topic (empty payload) is not an OFF command for every
        consumer (plan review finding 1)."""
        await self._client.publish(
            f"{self._base}/plan/demands/{demand_id}/setpoint", "0", retain=True
        )
        await self._client.publish(
            f"{self._base}/plan/demands/{demand_id}/on", "0", retain=True
        )

    async def _clear_demand_topics(self, demand_id: str) -> None:
        for leaf in ("setpoint", "on"):
            await self._client.publish(
                f"{self._base}/plan/demands/{demand_id}/{leaf}", "", retain=True
            )

    async def clear_expired(self, expired_ids: list[str]) -> None:
        """OFF first, then clear. An id withdrawn before it was ever mapped gets no
        mapped-but-inactive OFF from publish_plan, and a consumer that keeps its last
        value must still stop (#1 Medium 11 remainder)."""
        for demand_id in expired_ids:
            await self.publish_off(demand_id)
            await self._clear_demand_topics(demand_id)
