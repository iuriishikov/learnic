from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.entities.push_subscription.ids import PushSubscriptionID
from learnic.entities.push_subscription.models import PushSubscription
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.push_subscription import (
    push_subscriptions_table,
)


class PushSubscriptionGatewayAlchemy(PushSubscriptionGateway):
    """Postgres implementation of :class:`PushSubscriptionGateway`.

    Uses ``ON CONFLICT (endpoint) DO UPDATE`` so re-subscribing the
    same browser doesn't create duplicate rows; the keys (``p256dh``
    / ``auth``) and ``last_seen_at`` are refreshed with whatever the
    latest subscribe call carried. The update is guarded with
    ``WHERE user_id = excluded.user_id`` so a caller who presents
    another user's (leaked) endpoint cannot hijack that row — the
    conflict already blocks the insert and the guard blocks the
    ownership-reassigning update, so the attacker's subscribe is a
    no-op rather than a takeover.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def upsert(self, subscription: PushSubscription) -> None:
        stmt = pg_insert(push_subscriptions_table).values(
            oid=subscription.oid,
            user_id=subscription.user_id,
            endpoint=subscription.endpoint,
            p256dh=subscription.p256dh,
            auth=subscription.auth,
            user_agent=subscription.user_agent,
            created_at=subscription.created_at,
            last_seen_at=subscription.last_seen_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[push_subscriptions_table.c.endpoint],
            set_={
                "p256dh": stmt.excluded.p256dh,
                "auth": stmt.excluded.auth,
                "user_agent": stmt.excluded.user_agent,
                "last_seen_at": stmt.excluded.last_seen_at,
            },
            # Refuse to reassign a row owned by a different user — blocks
            # cross-user subscription hijack via a leaked endpoint.
            where=push_subscriptions_table.c.user_id == stmt.excluded.user_id,
        )
        await self._session.execute(stmt)

    @override
    async def delete_by_endpoint(
        self,
        endpoint: str,
        user_id: UserID,
    ) -> bool:
        result = await self._session.execute(
            sa.delete(push_subscriptions_table).where(
                push_subscriptions_table.c.endpoint == endpoint,
                push_subscriptions_table.c.user_id == user_id,
            ),
        )
        rowcount = getattr(result, "rowcount", 0)
        return bool(rowcount)

    @override
    async def list_for_user(
        self,
        user_id: UserID,
    ) -> Sequence[PushSubscription]:
        rows = (
            await self._session.execute(
                sa.select(
                    push_subscriptions_table.c.oid,
                    push_subscriptions_table.c.user_id,
                    push_subscriptions_table.c.endpoint,
                    push_subscriptions_table.c.p256dh,
                    push_subscriptions_table.c.auth,
                    push_subscriptions_table.c.user_agent,
                    push_subscriptions_table.c.created_at,
                    push_subscriptions_table.c.last_seen_at,
                )
                .where(push_subscriptions_table.c.user_id == user_id)
                .order_by(push_subscriptions_table.c.created_at.asc()),
            )
        ).all()
        return [
            PushSubscription(
                oid=PushSubscriptionID(row.oid),
                user_id=UserID(row.user_id),
                endpoint=row.endpoint,
                p256dh=row.p256dh,
                auth=row.auth,
                user_agent=row.user_agent,
                created_at=_ensure_aware(row.created_at),
                last_seen_at=_ensure_aware(row.last_seen_at),
            )
            for row in rows
        ]


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
