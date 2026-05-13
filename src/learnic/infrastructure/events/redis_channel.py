"""Generic Redis Pub/Sub adapter for per-product event channels.

One class, parameterised by:

* ``TPayload`` — the channel's payload union (e.g.
  ``ContentPayload``, ``ProductPayload``).
* The class-level ``CHANNEL_PREFIX`` — produces the Redis channel
  name ``"<prefix>:<product_id>"`` so different aggregates never
  share a backplane stream.
* The :meth:`_payload_from_wire` hook — channel-specific
  dispatch from the on-wire ``kind`` discriminator + payload
  dict back to a typed payload.

Concrete adapters (in ``infrastructure/collaboration/`` and
``infrastructure/product_events/``) inherit from this class,
fix the two channel-specific bits, and become trivial — the
serialisation, subscription loop, and lifecycle code is
written once here.
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import datetime
from typing import Any, ClassVar, Final, Generic, TypeVar, cast

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.events.channel import EventChannel
from learnic.application.common.events.events import Event
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

TPayload = TypeVar("TPayload")


class RedisEventChannel(EventChannel[TPayload], Generic[TPayload]):
    """Redis Pub/Sub implementation of :class:`EventChannel`.

    Each product gets its own Redis channel — ``CHANNEL_PREFIX``
    is set on the concrete subclass (e.g. ``"content"`` or
    ``"product"``). Subscribers open a private pubsub object and
    yield decoded :class:`Event` instances until the consumer
    closes the iterator.

    Subclasses override :meth:`_payload_from_wire` to dispatch on
    the ``kind`` discriminator and return the typed payload
    variant.
    """

    CHANNEL_PREFIX: ClassVar[str] = ""

    def __init__(self, redis: Redis) -> None:
        if not self.CHANNEL_PREFIX:
            msg = (
                f"{type(self).__name__}.CHANNEL_PREFIX must be set on "
                "the concrete subclass — generic RedisEventChannel "
                "cannot be instantiated directly."
            )
            raise RuntimeError(msg)
        self._redis: Final = redis

    def _payload_from_wire(
        self,
        kind: str,
        data: dict[str, Any],
    ) -> TPayload:
        """Reconstruct a typed payload from the on-wire dict.

        The dispatch is channel-specific (the union of payloads
        differs per channel), so concrete subclasses override
        this hook with a call to their channel's
        ``payload_from_wire(kind, data)`` function.
        """
        raise NotImplementedError

    def _channel(self, product_id: ProductID) -> str:
        return f"{self.CHANNEL_PREFIX}:{product_id}"

    @override
    async def publish(self, event: Event[TPayload]) -> None:
        await self._redis.publish(
            self._channel(event.product_id),
            json.dumps(
                {
                    # Every payload variant declares a class-level
                    # ``KIND`` constant — see ``HasPayloadKind`` in
                    # ``application/common/events/channel.py``. mypy
                    # cannot enforce this through the ``TPayload``
                    # bound (ClassVar invariance blocks the Protocol
                    # check), so the ``getattr`` keeps the access
                    # readable while the contract stays documented.
                    "kind": cast("Any", type(event.payload)).KIND,
                    "product_id": str(event.product_id),
                    "actor_id": str(event.actor_id),
                    "payload": asdict(cast("Any", event.payload)),
                    "occurred_at": event.occurred_at.isoformat(),
                },
            ),
        )

    @override
    async def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[Event[TPayload]]:
        channel = self._channel(product_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = json.loads(message["data"])
                yield Event(
                    payload=self._payload_from_wire(
                        raw["kind"],
                        raw["payload"],
                    ),
                    product_id=ProductID(uuid.UUID(raw["product_id"])),
                    actor_id=UserID(uuid.UUID(raw["actor_id"])),
                    occurred_at=datetime.fromisoformat(raw["occurred_at"]),
                )
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
