import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.product_collaboration_events.event_bus import (
    CollaborationEventBus,
)
from learnic.application.common.product_collaboration_events.events import (
    CollaborationEvent,
    CollaborationEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


def _channel(product_id: ProductID) -> str:
    return f"collab:{product_id}"


def _serialize(event: CollaborationEvent) -> str:
    return json.dumps(
        {
            "kind": event.kind.value,
            "product_id": str(event.product_id),
            "actor_id": str(event.actor_id),
            "payload": event.payload,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )


def _deserialize(data: Any) -> CollaborationEvent:  # noqa: ANN401
    payload = json.loads(data)
    return CollaborationEvent(
        kind=CollaborationEventKind(payload["kind"]),
        product_id=ProductID(uuid.UUID(payload["product_id"])),
        actor_id=UserID(uuid.UUID(payload["actor_id"])),
        payload=payload["payload"],
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )


class CollaborationEventBusRedis(CollaborationEventBus):
    """Redis Pub/Sub implementation of ``CollaborationEventBus``.

    Each product gets its own channel ``collab:{product_id}`` so a
    subscriber for product X never wakes up on changes to product Y.
    Same shape as :class:`ProductEventBusRedis` and the other
    redis-backed buses in this codebase — kept duplicated rather
    than abstracted because the cross-bus generalisation would
    obscure each topic's payload contract for marginal savings.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(self, event: CollaborationEvent) -> None:
        await self._redis.publish(
            _channel(event.product_id),
            _serialize(event),
        )

    @override
    async def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[CollaborationEvent]:
        channel = _channel(product_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield _deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
