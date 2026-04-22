import uuid
from datetime import datetime, timedelta, timezone
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.refresh_tokens import (
    IssuedRefreshToken,
    RefreshTokenRecord,
    RefreshTokenStore,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import SecurityConfig
from learnic.infrastructure.persistence.models.refresh_token import (
    refresh_tokens_table,
)
from learnic.infrastructure.security._tokens import (
    generate_raw_token,
    hash_token,
)


class RefreshTokenStoreAlchemy(RefreshTokenStore):
    """Postgres-backed refresh-token store with rotation + reuse detection."""

    def __init__(
        self,
        session: AsyncSession,
        config: SecurityConfig,
    ) -> None:
        self._session: Final = session
        self._ttl: Final = timedelta(
            seconds=config.refresh_token_ttl_seconds,
        )

    @override
    async def issue(
        self,
        user_id: UserID,
        family_id: uuid.UUID | None = None,
    ) -> IssuedRefreshToken:
        raw = generate_raw_token()
        token_hash = hash_token(raw)
        jti = uuid.uuid4()
        family = family_id or uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + self._ttl

        await self._session.execute(
            sa.insert(refresh_tokens_table).values(
                token_hash=token_hash,
                jti=jti,
                family_id=family,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        return IssuedRefreshToken(
            token=raw,
            record=RefreshTokenRecord(
                jti=jti,
                family_id=family,
                user_id=user_id,
                expires_at=expires_at,
            ),
        )

    @override
    async def rotate(self, presented: str) -> IssuedRefreshToken:
        token_hash = hash_token(presented)
        now = datetime.now(timezone.utc)

        row = (
            await self._session.execute(
                sa.select(
                    refresh_tokens_table.c.family_id,
                    refresh_tokens_table.c.user_id,
                    refresh_tokens_table.c.revoked_at,
                    refresh_tokens_table.c.expires_at,
                )
                .where(refresh_tokens_table.c.token_hash == token_hash)
                .with_for_update()
            )
        ).one_or_none()

        if row is None:
            raise InvalidTokenError

        if row.revoked_at is not None:
            # Reuse detected: kill the entire family.
            await self._revoke_family(row.family_id)
            raise InvalidTokenError

        if row.expires_at <= now:
            raise InvalidTokenError

        await self._session.execute(
            sa.update(refresh_tokens_table)
            .where(refresh_tokens_table.c.token_hash == token_hash)
            .values(revoked_at=now)
        )
        return await self.issue(UserID(row.user_id), family_id=row.family_id)

    @override
    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self._revoke_family(family_id)

    @override
    async def revoke_all_for_user(self, user_id: UserID) -> None:
        await self._session.execute(
            sa.update(refresh_tokens_table)
            .where(
                refresh_tokens_table.c.user_id == user_id,
                refresh_tokens_table.c.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

    @override
    async def resolve(self, presented: str) -> RefreshTokenRecord | None:
        token_hash = hash_token(presented)
        row = (
            await self._session.execute(
                sa.select(
                    refresh_tokens_table.c.jti,
                    refresh_tokens_table.c.family_id,
                    refresh_tokens_table.c.user_id,
                    refresh_tokens_table.c.expires_at,
                ).where(refresh_tokens_table.c.token_hash == token_hash)
            )
        ).one_or_none()
        if row is None:
            return None
        return RefreshTokenRecord(
            jti=row.jti,
            family_id=row.family_id,
            user_id=UserID(row.user_id),
            expires_at=row.expires_at,
        )

    async def _revoke_family(self, family_id: uuid.UUID) -> None:
        await self._session.execute(
            sa.update(refresh_tokens_table)
            .where(
                refresh_tokens_table.c.family_id == family_id,
                refresh_tokens_table.c.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
