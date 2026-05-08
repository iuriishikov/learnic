import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.presence.event_bus import PresenceEventBus
from learnic.application.common.presence.events import PresenceEvent
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID

CHANNEL: Final = "presence:events"


def _serialize(event: PresenceEvent) -> str:
    return json.dumps(
        {
            "user_id": str(event.user_id),
            "status": event.status.value,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )


def _deserialize(data: Any) -> PresenceEvent:  # noqa: ANN401
    payload = json.loads(data)
    return PresenceEvent(
        user_id=UserID(uuid.UUID(payload["user_id"])),
        status=PresenceStatus(payload["status"]),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )


class PresenceEventBusRedis(PresenceEventBus):
    """Redis Pub/Sub implementation of ``PresenceEventBus``.

    All events flow through a single channel (``CHANNEL``); each
    ``subscribe()`` call opens its own pubsub object and yields
    decoded :class:`PresenceEvent` instances until the consumer
    closes the iterator. The shared channel is the simplest fan-out
    that works correctly across multiple FastAPI processes.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(self, event: PresenceEvent) -> None:
        await self._redis.publish(CHANNEL, _serialize(event))

    @override
    async def subscribe(self) -> AsyncIterator[PresenceEvent]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield _deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
