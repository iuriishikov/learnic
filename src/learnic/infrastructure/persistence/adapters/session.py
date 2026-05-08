from datetime import datetime, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.session import (
    SessionsReader,
    SessionView,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.refresh_token import (
    refresh_tokens_table,
)


class SessionsReaderAlchemy(SessionsReader):
    """Reads active refresh-token families as user-facing sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def list_for_user(self, user_id: UserID) -> list[SessionView]:
        now = datetime.now(timezone.utc)
        active = refresh_tokens_table.alias("active")
        family = refresh_tokens_table.alias("family")

        created_at_subq = (
            sa.select(sa.func.min(family.c.issued_at))
            .where(family.c.family_id == active.c.family_id)
            .correlate(active)
            .scalar_subquery()
        )

        stmt = (
            sa.select(
                active.c.family_id,
                created_at_subq.label("created_at"),
                active.c.issued_at.label("last_used_at"),
                active.c.expires_at,
                active.c.ip_address,
                active.c.user_agent,
                active.c.device_label,
            )
            .where(
                active.c.user_id == user_id,
                active.c.revoked_at.is_(None),
                active.c.expires_at > now,
            )
            .order_by(active.c.issued_at.desc())
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            SessionView(
                family_id=row.family_id,
                created_at=row.created_at,
                last_used_at=row.last_used_at,
                expires_at=row.expires_at,
                ip_address=str(row.ip_address) if row.ip_address is not None else None,
                user_agent=row.user_agent,
                device_label=row.device_label,
            )
            for row in rows
        ]
