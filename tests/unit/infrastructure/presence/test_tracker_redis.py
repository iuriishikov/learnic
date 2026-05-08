import time
import uuid
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from learnic.entities.presence.constants import PRESENCE_TTL_SECONDS
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID
from learnic.infrastructure.presence.adapters.tracker_redis import (
    PresenceTrackerRedis,
    _key,
)


@pytest.fixture
def user_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def tracker(
    redis_client: Redis,
    fake_event_bus: AsyncMock,
) -> PresenceTrackerRedis:
    return PresenceTrackerRedis(redis=redis_client, event_bus=fake_event_bus)


class TestMarkOnline:
    async def test_makes_user_online(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")

        assert await tracker.is_online(user_id) is True

    async def test_first_connection_publishes_online_event(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        fake_event_bus: AsyncMock,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")

        fake_event_bus.publish.assert_awaited_once()
        event = fake_event_bus.publish.await_args.args[0]
        assert event.user_id == user_id
        assert event.status is PresenceStatus.ONLINE

    async def test_second_connection_does_not_publish_event(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        fake_event_bus: AsyncMock,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")
        fake_event_bus.publish.reset_mock()

        await tracker.mark_online(user_id, "conn-2")

        fake_event_bus.publish.assert_not_awaited()

    async def test_sets_key_ttl(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        redis_client: Redis,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")

        ttl = await redis_client.ttl(_key(user_id))
        assert ttl > 0


class TestMarkOffline:
    async def test_makes_single_connection_user_offline(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")

        await tracker.mark_offline(user_id, "conn-1")

        assert await tracker.is_online(user_id) is False

    async def test_last_connection_drop_publishes_offline_event(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        fake_event_bus: AsyncMock,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")
        fake_event_bus.publish.reset_mock()

        await tracker.mark_offline(user_id, "conn-1")

        fake_event_bus.publish.assert_awaited_once()
        event = fake_event_bus.publish.await_args.args[0]
        assert event.user_id == user_id
        assert event.status is PresenceStatus.OFFLINE

    async def test_dropping_one_of_many_connections_does_not_publish(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        fake_event_bus: AsyncMock,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")
        await tracker.mark_online(user_id, "conn-2")
        fake_event_bus.publish.reset_mock()

        await tracker.mark_offline(user_id, "conn-1")

        assert await tracker.is_online(user_id) is True
        fake_event_bus.publish.assert_not_awaited()

    async def test_offline_for_unknown_connection_is_safe(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
    ) -> None:
        # idempotent: already-offline user dropping a phantom session
        # must not crash and must not change state
        await tracker.mark_offline(user_id, "phantom")
        assert await tracker.is_online(user_id) is False


class TestHeartbeat:
    async def test_does_not_publish_event(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        fake_event_bus: AsyncMock,
    ) -> None:
        await tracker.mark_online(user_id, "conn-1")
        fake_event_bus.publish.reset_mock()

        await tracker.heartbeat(user_id, "conn-1")

        fake_event_bus.publish.assert_not_awaited()

    async def test_only_refreshes_existing_connection(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        redis_client: Redis,
    ) -> None:
        # heartbeat uses ZADD XX — must not register an unknown conn
        await tracker.heartbeat(user_id, "phantom")

        assert await redis_client.zcard(_key(user_id)) == 0


class TestIsOnline:
    async def test_false_for_unknown_user(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
    ) -> None:
        assert await tracker.is_online(user_id) is False

    async def test_drops_stale_connections(
        self,
        tracker: PresenceTrackerRedis,
        user_id: UserID,
        redis_client: Redis,
    ) -> None:
        # write a connection record with a stale score directly to
        # bypass mark_online — simulates a session whose heartbeat
        # never refreshed
        stale = time.time() - PRESENCE_TTL_SECONDS - 1
        await redis_client.zadd(_key(user_id), {"stale": stale})

        assert await tracker.is_online(user_id) is False
        assert await redis_client.zcard(_key(user_id)) == 0


class TestFilterOnline:
    async def test_empty_input_returns_empty(
        self,
        tracker: PresenceTrackerRedis,
    ) -> None:
        assert await tracker.filter_online([]) == set()

    async def test_returns_subset_currently_online(
        self,
        tracker: PresenceTrackerRedis,
    ) -> None:
        a = UserID(uuid.uuid4())
        b = UserID(uuid.uuid4())
        c = UserID(uuid.uuid4())
        await tracker.mark_online(a, "ca")
        await tracker.mark_online(c, "cc")

        online = await tracker.filter_online([a, b, c])

        assert online == {a, c}


class TestKeyIsolation:
    async def test_users_dont_leak_into_each_other(
        self,
        tracker: PresenceTrackerRedis,
    ) -> None:
        a = UserID(uuid.uuid4())
        b = UserID(uuid.uuid4())

        await tracker.mark_online(a, "conn-1")

        assert await tracker.is_online(a) is True
        assert await tracker.is_online(b) is False
