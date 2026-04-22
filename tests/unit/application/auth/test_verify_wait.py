from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.verify_wait import (
    VerifyWaitCommand,
    VerifyWaitCommandHandler,
)
from learnic.application.common.errors import InvalidTokenError


async def test_verify_wait_returns_not_ready_while_unverified(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
    unverified_user,
) -> None:
    fake_signup_sessions.resolve.return_value = unverified_user.oid
    fake_user_gateway.with_id.return_value = unverified_user

    handler = VerifyWaitCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        signup_sessions=fake_signup_sessions,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )
    result = await handler.run(VerifyWaitCommand(signup_session_token="raw"))

    assert result.ready is False
    assert result.token_pair is None
    fake_signup_sessions.revoke.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_verify_wait_issues_tokens_after_verification(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
    verified_user,
) -> None:
    fake_signup_sessions.resolve.return_value = verified_user.oid
    fake_user_gateway.with_id.return_value = verified_user

    handler = VerifyWaitCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        signup_sessions=fake_signup_sessions,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )
    result = await handler.run(VerifyWaitCommand(signup_session_token="raw"))

    assert result.ready is True
    assert result.token_pair is not None
    assert result.token_pair.access_token == "jwt"
    fake_signup_sessions.revoke.assert_awaited_once_with("raw")
    fake_transaction.commit.assert_awaited_once()


async def test_verify_wait_invalid_signup_session_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
) -> None:
    fake_signup_sessions.resolve.return_value = None

    handler = VerifyWaitCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        signup_sessions=fake_signup_sessions,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
    )
    with pytest.raises(InvalidTokenError):
        await handler.run(VerifyWaitCommand(signup_session_token="raw"))
