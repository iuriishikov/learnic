from datetime import datetime
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.email_sending import (
    EmailSendingGateway,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.email_sending import (
    email_sendings_table,
)


class EmailSendingMapperAlchemy(EmailSendingGateway):
    """Postgres-backed :class:`EmailSendingGateway`.

    The advisory lock mirrors :class:`StorageQuotaLockAlchemy`: a
    transaction-scoped ``pg_advisory_xact_lock`` keyed on a 64-bit
    hash of the actor UUID via ``hashtextextended``. The key string is
    namespaced with an ``email_send:`` prefix so it never collides
    with locks taken elsewhere for the same user (e.g. the storage
    quota lock, which hashes the bare UUID).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def acquire_actor_lock(self, actor_id: UserID) -> None:
        await self._session.execute(
            sa.text(
                "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))",
            ),
            {"k": f"email_send:{actor_id}"},
        )

    @override
    async def count_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(email_sendings_table)
            .where(
                email_sendings_table.c.actor_id == actor_id,
                email_sendings_table.c.sent_at >= since,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
