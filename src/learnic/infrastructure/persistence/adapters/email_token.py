from datetime import datetime, timedelta, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.email_token import (
    email_tokens_table,
)
from learnic.infrastructure.security._tokens import (
    generate_raw_token,
    hash_token,
)


class EmailTokenStoreAlchemy(EmailTokenStore):
    """Single-use email tokens (verification and password reset)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def issue(
        self,
        user_id: UserID,
        purpose: EmailTokenPurpose,
        ttl_seconds: int,
    ) -> str:
        now = datetime.now(timezone.utc)
        # Invalidate any earlier active tokens for this (user, purpose)
        # so that a resend supersedes older links.
        await self._session.execute(
            sa.update(email_tokens_table)
            .where(
                email_tokens_table.c.user_id == user_id,
                email_tokens_table.c.purpose == purpose.value,
                email_tokens_table.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )

        raw = generate_raw_token()
        await self._session.execute(
            sa.insert(email_tokens_table).values(
                token_hash=hash_token(raw),
                user_id=user_id,
                purpose=purpose.value,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
        )
        return raw

    @override
    async def consume(
        self,
        raw_token: str,
        purpose: EmailTokenPurpose,
    ) -> UserID:
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)

        row = (
            await self._session.execute(
                sa.select(
                    email_tokens_table.c.user_id,
                    email_tokens_table.c.purpose,
                    email_tokens_table.c.expires_at,
                    email_tokens_table.c.consumed_at,
                )
                .where(email_tokens_table.c.token_hash == token_hash)
                .with_for_update()
            )
        ).one_or_none()

        if row is None:
            raise InvalidTokenError
        if row.consumed_at is not None:
            raise InvalidTokenError
        if row.expires_at <= now:
            raise InvalidTokenError
        if row.purpose != purpose.value:
            raise InvalidTokenError

        await self._session.execute(
            sa.update(email_tokens_table)
            .where(email_tokens_table.c.token_hash == token_hash)
            .values(consumed_at=now)
        )
        return UserID(row.user_id)
