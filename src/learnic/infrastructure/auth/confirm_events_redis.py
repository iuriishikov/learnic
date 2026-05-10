import json
from collections.abc import AsyncIterator
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.auth.confirm_events import (
    ConfirmEvent,
    ConfirmEventBus,
    ConfirmEventKind,
)
from learnic.entities.user.models import UserID


def _channel(user_id: UserID) -> str:
    return f"confirm:{user_id}"


def _serialize(event: ConfirmEvent) -> str:
    return json.dumps(
        {
            "kind": event.kind.value,
            "purpose": event.purpose,
        },
    )


def _deserialize(raw: Any, user_id: UserID) -> ConfirmEvent:  # noqa: ANN401
    payload = json.loads(raw)
    return ConfirmEvent(
        user_id=user_id,
        kind=ConfirmEventKind(payload["kind"]),
        purpose=str(payload["purpose"]),
    )


class ConfirmEventBusRedis(ConfirmEventBus):
    """Redis pub/sub implementation of :class:`ConfirmEventBus`.

    Channel-per-user (``confirm:{user_id}``). Mirrors the shape used
    by the notification and product event buses — kept duplicated
    rather than abstracted because the payload contracts diverge.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(self, event: ConfirmEvent) -> None:
        await self._redis.publish(_channel(event.user_id), _serialize(event))

    @override
    async def subscribe(
        self,
        user_id: UserID,
    ) -> AsyncIterator[ConfirmEvent]:
        channel = _channel(user_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield _deserialize(message["data"], user_id)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
