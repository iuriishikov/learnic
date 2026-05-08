import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from redis.asyncio import Redis

from learnic.application.common.presence.events import PresenceEvent
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID
from learnic.infrastructure.presence.adapters.event_bus_redis import (
    CHANNEL,
    PresenceEventBusRedis,
)


@pytest.fixture
def event() -> PresenceEvent:
    return PresenceEvent(
        user_id=UserID(uuid.uuid4()),
        status=PresenceStatus.ONLINE,
        occurred_at=datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc),
    )


async def test_publish_writes_json_to_channel(
    redis_client: Redis,
    event: PresenceEvent,
) -> None:
    bus = PresenceEventBusRedis(redis=redis_client)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(CHANNEL)
    # consume the subscribe acknowledgement so the next listen() call
    # returns the message we publish below
    await pubsub.get_message(timeout=1.0)
    try:
        await bus.publish(event)

        msg = await pubsub.get_message(timeout=1.0)
        assert msg is not None
        assert msg["type"] == "message"
        payload = json.loads(msg["data"])
        assert payload == {
            "user_id": str(event.user_id),
            "status": "online",
            "occurred_at": event.occurred_at.isoformat(),
        }
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()  # type: ignore[no-untyped-call]


async def test_subscribe_yields_published_events(
    redis_client: Redis,
    event: PresenceEvent,
) -> None:
    bus = PresenceEventBusRedis(redis=redis_client)
    received: list[PresenceEvent] = []

    async def consumer() -> None:
        async for ev in bus.subscribe():
            received.append(ev)
            if len(received) == 1:
                return

    task = asyncio.create_task(consumer())
    # give the subscriber time to register before publishing — Redis
    # Pub/Sub does not retain messages for late subscribers
    await asyncio.sleep(0.05)

    await bus.publish(event)

    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    got = received[0]
    assert got.user_id == event.user_id
    assert got.status is event.status
    assert got.occurred_at == event.occurred_at


async def test_subscribe_filters_non_message_frames(
    redis_client: Redis,
    event: PresenceEvent,
) -> None:
    # subscribe acknowledgements arrive on the same pubsub stream
    # as actual messages — make sure they're filtered out
    bus = PresenceEventBusRedis(redis=redis_client)
    received: list[PresenceEvent] = []

    async def consumer() -> None:
        async for ev in bus.subscribe():
            received.append(ev)
            return

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.05)
    await bus.publish(event)
    await asyncio.wait_for(task, timeout=2.0)

    # exactly one message — the subscribe ack didn't slip through
    assert len(received) == 1
