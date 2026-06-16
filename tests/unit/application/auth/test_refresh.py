import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.refresh import (
    RefreshCommand,
    RefreshCommandHandler,
)
from learnic.application.common.errors import (
    InvalidTokenError,
    RefreshTokenReuseError,
)
from learnic.application.common.security.refresh_tokens import (
    IssuedRefreshToken,
    RefreshTokenRecord,
)
from learnic.entities.user.models import UserID


def _issued_refresh() -> IssuedRefreshToken:
    return IssuedRefreshToken(
        token="raw-refresh",
        record=RefreshTokenRecord(
            jti=uuid.uuid4(),
            family_id=uuid.uuid4(),
            user_id=UserID(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ),
    )


async def test_refresh_success_issues_pair_and_commits(
    fake_transaction: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
) -> None:
    fake_refresh_store.rotate.return_value = _issued_refresh()

    handler = RefreshCommandHandler(
        transaction=fake_transaction,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )
    pair = await handler.run(RefreshCommand(refresh_token="valid"))

    assert pair.access_token == "jwt"
    assert pair.refresh_token == "raw-refresh"
    fake_transaction.commit.assert_awaited_once()
    fake_refresh_store.revoke_family.assert_not_awaited()


async def test_refresh_reuse_commits_family_revocation_then_raises(
    fake_transaction: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
) -> None:
    # rotate() detects reuse: it has already issued the family-wide
    # revocation (uncommitted) and signals via RefreshTokenReuseError.
    fake_refresh_store.rotate.side_effect = RefreshTokenReuseError

    handler = RefreshCommandHandler(
        transaction=fake_transaction,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )

    with pytest.raises(InvalidTokenError) as exc_info:
        await handler.run(RefreshCommand(refresh_token="stolen-reused"))

    # The revocation must be committed even though the request fails —
    # the original bug was that the request rollback discarded it.
    fake_transaction.commit.assert_awaited_once()
    # Clients see a plain InvalidToken (401), never the internal
    # RefreshTokenReuse signal type.
    assert exc_info.type is InvalidTokenError


async def test_refresh_unknown_token_does_not_commit(
    fake_transaction: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
) -> None:
    fake_refresh_store.rotate.side_effect = InvalidTokenError

    handler = RefreshCommandHandler(
        transaction=fake_transaction,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )

    with pytest.raises(InvalidTokenError):
        await handler.run(RefreshCommand(refresh_token="bogus"))

    # A non-reuse invalid token must not trigger a spurious commit.
    fake_transaction.commit.assert_not_awaited()
