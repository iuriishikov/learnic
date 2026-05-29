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

    The prune + (de)register + recount runs in a single MULTI/EXEC
    pipeline so the edge decision is atomic across concurrent
    connections and replicas — no duplicate ONLINE and no missed
    OFFLINE from a racing connect/disconnect. The PUBLISH itself
    happens just after EXEC; making the publish of two simultaneous
    cross-replica transitions strictly ordered would require doing it
    inside the script (a Lua ``EVAL`` that ends with ``PUBLISH``).
    """

    def __init__(self, redis: Redis, event_bus: PresenceEventBus) -> None:
        self._redis: Final = redis
        self._event_bus: Final = event_bus

    @override
    async def mark_online(self, user_id: UserID, conn_id: str) -> None:
        now = time.time()
        cutoff = now - PRESENCE_TTL_SECONDS
        key = _key(user_id)
        # Prune + add + recount in one MULTI/EXEC so the edge decision
        # is atomic: two connections racing (possibly on different
        # replicas) cannot both observe an empty set and both publish
        # ONLINE, and a concurrent last-disconnect cannot make us
        # miscount. ``count_after - added`` is the live count that
        # existed BEFORE this connection was added.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {conn_id: now})
            pipe.zcard(key)
            pipe.expire(key, _KEY_TTL_SECONDS)
            _, added, count_after, _ = await pipe.execute()
        if count_after - added == 0:
            await self._event_bus.publish(
                PresenceEvent(
                    user_id=user_id,
                    status=PresenceStatus.ONLINE,
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

    @override
    async def mark_offline(self, user_id: UserID, conn_id: str) -> None:
        now = time.time()
        cutoff = now - PRESENCE_TTL_SECONDS
        key = _key(user_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zrem(key, conn_id)
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            removed, _, count_after = await pipe.execute()
        # Only the connection that actually removed a live member and
        # left the set empty announces OFFLINE — guards a phantom or
        # duplicate disconnect against publishing a spurious event.
        if removed and count_after == 0:
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
