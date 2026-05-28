import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.cursors.event_bus import CursorsEventBus
from learnic.application.common.cursors.events import (
    CursorsEvent,
    CursorsEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

# One pub/sub channel per product so a busy product doesn't fan
# out to unrelated subscribers. The WS forward loop subscribes to
# exactly the channel for its product.
_CHANNEL_PREFIX: Final = "cursors:channel"


def _channel(product_id: ProductID) -> str:
    return f"{_CHANNEL_PREFIX}:{product_id}"


def _serialize(event: CursorsEvent) -> str:
    return json.dumps(
        {
            "kind": event.kind.value,
            "product_id": str(event.product_id),
            "user_id": str(event.user_id),
            "field_id": event.field_id,
            "action": event.action,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )


def _deserialize(data: Any) -> CursorsEvent:  # noqa: ANN401
    payload = json.loads(data)
    return CursorsEvent(
        kind=CursorsEventKind(payload["kind"]),
        product_id=ProductID(uuid.UUID(payload["product_id"])),
        user_id=UserID(uuid.UUID(payload["user_id"])),
        field_id=payload["field_id"],
        action=payload["action"],
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )


class CursorsEventBusRedis(CursorsEventBus):
    """Redis Pub/Sub implementation of ``CursorsEventBus``.

    Each ``ProductID`` gets its own channel
    (``cursors:channel:{product_id}``). Subscribers iterate
    ``subscribe()`` for one product; each open call constructs its
    own pubsub object and tears it down on consumer cancellation.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(self, event: CursorsEvent) -> None:
        await self._redis.publish(
            _channel(event.product_id),
            _serialize(event),
        )

    @override
    async def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[CursorsEvent]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_channel(product_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield _deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(_channel(product_id))
            await pubsub.aclose()  # type: ignore[no-untyped-call]
