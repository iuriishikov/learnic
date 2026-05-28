import json
import uuid
from collections.abc import Awaitable
from datetime import datetime
from typing import Any, Final, cast

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.cursors.state import (
    CursorSnapshot,
    CursorsState,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

# One hash per product, fields keyed by user_id. Storing the lot in
# a single hash makes ``snapshot`` a single ``HGETALL`` instead of
# a SCAN over per-user keys.
_STATE_KEY_PREFIX: Final = "cursors:state"


def _state_key(product_id: ProductID) -> str:
    return f"{_STATE_KEY_PREFIX}:{product_id}"


def _encode(
    *,
    conn_id: str,
    field_id: str,
    action: str | None,
    now: datetime,
) -> str:
    return json.dumps(
        {
            "conn_id": conn_id,
            "field_id": field_id,
            "action": action,
            "last_seen": now.isoformat(),
        },
    )


def _decode(raw: Any) -> dict[str, Any] | None:  # noqa: ANN401
    if raw is None:
        return None
    try:
        decoded: Any = json.loads(raw)
    except (ValueError, TypeError) as _exc:  # noqa: F841
        return None
    if not isinstance(decoded, dict):
        return None
    return decoded


class CursorsStateRedis(CursorsState):
    """Redis-backed implementation of ``CursorsState``.

    Lazy staleness: ``snapshot`` filters and HDEL-prunes entries
    older than ``stale_after_seconds`` inline. There is no
    background cleanup worker — the WS-on-connect path is also
    the cleanup path, which is enough because the SPA carries its
    own short-horizon eviction timer and any "stale Redis entry"
    is invisible to users until the next subscribe.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish_at(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
        field_id: str,
        action: str | None,
        now: datetime,
    ) -> None:
        # redis-py's H-commands type their return as
        # ``Awaitable[int] | int`` — strict mypy can't narrow the
        # union, so cast at the boundary.
        await cast(
            "Awaitable[int]",
            self._redis.hset(
                _state_key(product_id),
                str(user_id),
                _encode(
                    conn_id=conn_id,
                    field_id=field_id,
                    action=action,
                    now=now,
                ),
            ),
        )

    @override
    async def publish_leave(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
        field_id: str,
    ) -> bool:
        raw = await cast(
            "Awaitable[str | None]",
            self._redis.hget(_state_key(product_id), str(user_id)),
        )
        decoded = _decode(raw)
        if decoded is None:
            return False
        # Same-user "I left field X" only fires when the current
        # stored entry matches both the connection AND the field;
        # a fresher tab on a different field is unaffected.
        if decoded.get("conn_id") != conn_id or decoded.get("field_id") != field_id:
            return False
        removed = await cast(
            "Awaitable[int]",
            self._redis.hdel(_state_key(product_id), str(user_id)),
        )
        return removed > 0

    @override
    async def mark_disconnect(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
    ) -> bool:
        raw = await cast(
            "Awaitable[str | None]",
            self._redis.hget(_state_key(product_id), str(user_id)),
        )
        decoded = _decode(raw)
        if decoded is None:
            return False
        # Tab-1 closing doesn't wipe Tab-2's cursor — only the
        # connection that "owns" the stored entry can clear it.
        if decoded.get("conn_id") != conn_id:
            return False
        removed = await cast(
            "Awaitable[int]",
            self._redis.hdel(_state_key(product_id), str(user_id)),
        )
        return removed > 0

    @override
    async def snapshot(
        self,
        product_id: ProductID,
        *,
        exclude_user_id: UserID,
        now: datetime,
        stale_after_seconds: int,
    ) -> list[CursorSnapshot]:
        raw_all = await cast(
            "Awaitable[dict[str, str]]",
            self._redis.hgetall(_state_key(product_id)),
        )
        if not raw_all:
            return []
        cutoff = now.timestamp() - stale_after_seconds
        fresh: list[CursorSnapshot] = []
        stale_fields: list[str] = []
        exclude_str = str(exclude_user_id)
        for field, raw in raw_all.items():
            if field == exclude_str:
                continue
            decoded = _decode(raw)
            if decoded is None:
                stale_fields.append(field)
                continue
            try:
                last_seen = datetime.fromisoformat(decoded["last_seen"])
            except (KeyError, ValueError, TypeError) as _exc:  # noqa: F841
                stale_fields.append(field)
                continue
            if last_seen.timestamp() < cutoff:
                stale_fields.append(field)
                continue
            try:
                snapshot_user_id = UserID(uuid.UUID(field))
            except (ValueError, AttributeError) as _exc:  # noqa: F841
                stale_fields.append(field)
                continue
            field_id = decoded.get("field_id")
            if not isinstance(field_id, str):
                stale_fields.append(field)
                continue
            action = decoded.get("action")
            if action is not None and not isinstance(action, str):
                action = None
            fresh.append(
                CursorSnapshot(
                    user_id=snapshot_user_id,
                    field_id=field_id,
                    action=action,
                    updated_at=last_seen,
                ),
            )
        if stale_fields:
            await cast(
                "Awaitable[int]",
                self._redis.hdel(_state_key(product_id), *stale_fields),
            )
        return fresh
