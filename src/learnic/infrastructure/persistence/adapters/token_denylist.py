import uuid
from datetime import datetime, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.infrastructure.persistence.models.token_denylist import (
    family_denylist_table,
)


class TokenDenylistAlchemy(TokenDenylist):
    """Postgres-backed family-level access-token denylist."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def is_family_denied(self, family_id: uuid.UUID) -> bool:
        row = (
            await self._session.execute(
                sa.select(sa.literal(1)).where(
                    family_denylist_table.c.family_id == family_id,
                    family_denylist_table.c.expires_at
                    > datetime.now(timezone.utc),
                )
            )
        ).first()
        return row is not None

    @override
    async def deny_family(
        self,
        family_id: uuid.UUID,
        expires_at: datetime,
    ) -> None:
        stmt = pg_insert(family_denylist_table).values(
            family_id=family_id,
            expires_at=expires_at,
        )
        await self._session.execute(
            stmt.on_conflict_do_update(
                index_elements=["family_id"],
                set_={"expires_at": expires_at},
            ),
        )

    @override
    async def cleanup_expired(self) -> int:
        result = await self._session.execute(
            sa.delete(family_denylist_table).where(
                family_denylist_table.c.expires_at
                <= datetime.now(timezone.utc),
            )
        )
        rowcount: int | None = getattr(result, "rowcount", None)
        return rowcount or 0
