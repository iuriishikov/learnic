from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.email_tokens import EmailTokenPurpose


async def test_verify_email_consumes_token_and_marks_user(
    fake_transaction: AsyncMock,
    fake_email_tokens: AsyncMock,
    fake_user_gateway: AsyncMock,
    unverified_user,
) -> None:
    fake_email_tokens.consume.return_value = unverified_user.oid
    fake_user_gateway.with_id.return_value = unverified_user

    handler = VerifyEmailCommandHandler(
        transaction=fake_transaction,
        email_tokens=fake_email_tokens,
        user_gateway=fake_user_gateway,
    )
    await handler.run(VerifyEmailCommand(token="raw"))

    fake_email_tokens.consume.assert_awaited_once_with("raw", EmailTokenPurpose.VERIFY)
    assert unverified_user.email_verified is True
    fake_transaction.commit.assert_awaited_once()


async def test_verify_email_missing_user_raises(
    fake_transaction: AsyncMock,
    fake_email_tokens: AsyncMock,
    fake_user_gateway: AsyncMock,
    unverified_user,
) -> None:
    fake_email_tokens.consume.return_value = unverified_user.oid
    fake_user_gateway.with_id.return_value = None

    handler = VerifyEmailCommandHandler(
        transaction=fake_transaction,
        email_tokens=fake_email_tokens,
        user_gateway=fake_user_gateway,
    )
    with pytest.raises(InvalidTokenError):
        await handler.run(VerifyEmailCommand(token="raw"))

    fake_transaction.commit.assert_not_called()
