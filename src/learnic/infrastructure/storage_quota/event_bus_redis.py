import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
    StorageQuotaEventKind,
    StorageQuotaUsageEvent,
)
from learnic.entities.billing.ids import PlanCode
from learnic.entities.user.models import UserID


def _channel(quota_owner_id: UserID) -> str:
    return f"storage-quota:{quota_owner_id}"


class StorageQuotaEventBusRedis(StorageQuotaEventBus):
    """Redis pub/sub implementation of :class:`StorageQuotaEventBus`.

    Channel-per-owner (``storage-quota:{user_id}``) so a connected
    user only wakes up on their own pool's changes. The payload is
    a flat snapshot — no per-kind dispatch needed.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(
        self,
        quota_owner_id: UserID,
        event: StorageQuotaUsageEvent,
    ) -> None:
        await self._redis.publish(
            _channel(quota_owner_id),
            self._serialize(event),
        )

    @override
    async def subscribe(
        self,
        quota_owner_id: UserID,
    ) -> AsyncIterator[StorageQuotaUsageEvent]:
        channel = _channel(quota_owner_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield self._deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    # --------------------------- internals --------------------------- #

    def _serialize(self, event: StorageQuotaUsageEvent) -> str:
        return json.dumps(
            {
                "kind": event.kind.value,
                "plan_code": str(event.plan_code),
                "storage_bytes_max": event.storage_bytes_max,
                "storage_bytes_used": event.storage_bytes_used,
                "storage_bytes_remaining": event.storage_bytes_remaining,
                "occurred_at": event.occurred_at.isoformat(),
            },
        )

    def _deserialize(self, raw: Any) -> StorageQuotaUsageEvent:  # noqa: ANN401
        payload = json.loads(raw)
        return StorageQuotaUsageEvent(
            plan_code=PlanCode(payload["plan_code"]),
            storage_bytes_max=payload["storage_bytes_max"],
            storage_bytes_used=payload["storage_bytes_used"],
            storage_bytes_remaining=payload["storage_bytes_remaining"],
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            kind=StorageQuotaEventKind(payload["kind"]),
        )
