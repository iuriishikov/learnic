from datetime import datetime, timedelta, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.signup_session import (
    signup_sessions_table,
)
from learnic.infrastructure.security._tokens import (
    generate_raw_token,
    hash_token,
)


class SignupSessionStoreAlchemy(SignupSessionStore):
    """Postgres-backed store for the browser-scoped signup marker."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def issue(self, user_id: UserID, ttl_seconds: int) -> str:
        raw = generate_raw_token()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        await self._session.execute(
            sa.insert(signup_sessions_table).values(
                token_hash=hash_token(raw),
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        return raw

    @override
    async def resolve(self, raw_token: str) -> UserID | None:
        now = datetime.now(timezone.utc)
        row = (
            await self._session.execute(
                sa.select(signup_sessions_table.c.user_id).where(
                    signup_sessions_table.c.token_hash == hash_token(raw_token),
                    signup_sessions_table.c.expires_at > now,
                )
            )
        ).one_or_none()
        return UserID(row.user_id) if row is not None else None

    @override
    async def revoke(self, raw_token: str) -> None:
        await self._session.execute(
            sa.delete(signup_sessions_table).where(
                signup_sessions_table.c.token_hash == hash_token(raw_token)
            )
        )
