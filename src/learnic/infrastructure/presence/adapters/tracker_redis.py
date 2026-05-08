import time
from datetime import datetime, timezone
from typing import Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.presence.event_bus import PresenceEventBus
from learnic.application.common.presence.events import PresenceEvent
from learnic.application.common.presence.tracker import PresenceTracker
from learnic.entities.presence.constants import PRESENCE_TTL_SECONDS
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID

_KEY_TTL_SECONDS: Final = PRESENCE_TTL_SECONDS * 2


def _key(user_id: UserID) -> str:
    return f"presence:user:{user_id}"


class PresenceTrackerRedis(PresenceTracker):
    """Redis-backed implementation of ``PresenceTracker``.

    Each user has a sorted set ``presence:user:{user_id}`` whose
    members are connection ids and whose scores are the unix-timestamp
    of the last heartbeat. ``is_online`` first prunes entries older
    than ``PRESENCE_TTL_SECONDS`` and then checks set cardinality.

    Edge transitions (first connection in / last connection out) are
    published to the injected :class:`PresenceEventBus`. Subsequent
    connections of an already-online user produce no events.
    """

    def __init__(self, redis: Redis, event_bus: PresenceEventBus) -> None:
        self._redis: Final = redis
        self._event_bus: Final = event_bus

    @override
    async def mark_online(self, user_id: UserID, conn_id: str) -> None:
        was_online = await self.is_online(user_id)
        await self._redis.zadd(_key(user_id), {conn_id: time.time()})
        await self._redis.expire(_key(user_id), _KEY_TTL_SECONDS)
        if not was_online:
            await self._event_bus.publish(
                PresenceEvent(
                    user_id=user_id,
                    status=PresenceStatus.ONLINE,
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

    @override
    async def mark_offline(self, user_id: UserID, conn_id: str) -> None:
        await self._redis.zrem(_key(user_id), conn_id)
        if not await self.is_online(user_id):
            await self._event_bus.publish(
                PresenceEvent(
                    user_id=user_id,
                    status=PresenceStatus.OFFLINE,
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

    @override
    async def heartbeat(self, user_id: UserID, conn_id: str) -> None:
        await self._redis.zadd(
            _key(user_id),
            {conn_id: time.time()},
            xx=True,
        )
        await self._redis.expire(_key(user_id), _KEY_TTL_SECONDS)

    @override
    async def is_online(self, user_id: UserID) -> bool:
        cutoff = time.time() - PRESENCE_TTL_SECONDS
        await self._redis.zremrangebyscore(_key(user_id), 0, cutoff)
        count: int = await self._redis.zcard(_key(user_id))
        return count > 0

    @override
    async def filter_online(
        self,
        user_ids: list[UserID],
    ) -> set[UserID]:
        if not user_ids:
            return set()
        cutoff = time.time() - PRESENCE_TTL_SECONDS
        async with self._redis.pipeline(transaction=False) as pipe:
            for user_id in user_ids:
                pipe.zremrangebyscore(_key(user_id), 0, cutoff)
                pipe.zcard(_key(user_id))
            results = await pipe.execute()
        return {
            user_id
            for user_id, count in zip(user_ids, results[1::2], strict=True)
            if count > 0
        }
