import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis

from learnic.application.common.product_collaboration_events.events import (
    CollaborationEvent,
    CollaborationEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.product_collaboration_events.event_bus_redis import (
    CollaborationEventBusRedis,
)


@pytest.fixture
def event() -> CollaborationEvent:
    return CollaborationEvent(
        kind=CollaborationEventKind.INVITED,
        product_id=ProductID(uuid.uuid4()),
        actor_id=UserID(uuid.uuid4()),
        payload={
            "collaboration_id": str(
                ProductCollaborationID(uuid.uuid4()),
            ),
            "collaborator_id": str(UserID(uuid.uuid4())),
        },
        occurred_at=datetime(
            2026,
            5,
            7,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    )


async def test_publish_writes_json_to_per_product_channel(
    redis_client: Redis,
    event: CollaborationEvent,
) -> None:
    bus = CollaborationEventBusRedis(redis=redis_client)
    channel = f"collab:{event.product_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    await pubsub.get_message(timeout=1.0)
    try:
        await bus.publish(event)

        msg = await pubsub.get_message(timeout=1.0)
        assert msg is not None
        assert msg["type"] == "message"
        payload = json.loads(msg["data"])
        assert payload == {
            "kind": "invited",
            "product_id": str(event.product_id),
            "actor_id": str(event.actor_id),
            "payload": event.payload,
            "occurred_at": event.occurred_at.isoformat(),
        }
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()  # type: ignore[no-untyped-call]


async def test_subscribe_yields_only_matching_product_events(
    redis_client: Redis,
    event: CollaborationEvent,
) -> None:
    bus = CollaborationEventBusRedis(redis=redis_client)
    received: list[CollaborationEvent] = []

    async def consumer() -> None:
        async for ev in bus.subscribe(event.product_id):
            received.append(ev)
            if len(received) == 1:
                return

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)

    other_event = CollaborationEvent(
        kind=CollaborationEventKind.INVITED,
        product_id=ProductID(uuid.uuid4()),
        actor_id=event.actor_id,
        payload={"collaboration_id": str(uuid.uuid4())},
        occurred_at=event.occurred_at,
    )
    await bus.publish(other_event)
    await bus.publish(event)
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0].product_id == event.product_id
    assert received[0].kind is CollaborationEventKind.INVITED
