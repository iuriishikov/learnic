from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)
from learnic.application.common.auth.confirm_events import (
    ConfirmEventKind,
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
    fake_confirm_events = AsyncMock()

    handler = VerifyEmailCommandHandler(
        transaction=fake_transaction,
        email_tokens=fake_email_tokens,
        user_gateway=fake_user_gateway,
        confirm_events=fake_confirm_events,
    )
    await handler.run(VerifyEmailCommand(token="raw"))

    fake_email_tokens.consume.assert_awaited_once_with("raw", EmailTokenPurpose.VERIFY)
    assert unverified_user.email_verified is True
    fake_transaction.commit.assert_awaited_once()
    fake_confirm_events.publish.assert_awaited_once()
    published = fake_confirm_events.publish.await_args.args[0]
    assert published.user_id == unverified_user.oid
    assert published.kind is ConfirmEventKind.CONFIRMED
    assert published.purpose == EmailTokenPurpose.VERIFY.value


async def test_verify_email_missing_user_raises(
    fake_transaction: AsyncMock,
    fake_email_tokens: AsyncMock,
    fake_user_gateway: AsyncMock,
    unverified_user,
) -> None:
    fake_email_tokens.consume.return_value = unverified_user.oid
    fake_user_gateway.with_id.return_value = None
    fake_confirm_events = AsyncMock()

    handler = VerifyEmailCommandHandler(
        transaction=fake_transaction,
        email_tokens=fake_email_tokens,
        user_gateway=fake_user_gateway,
        confirm_events=fake_confirm_events,
    )
    with pytest.raises(InvalidTokenError):
        await handler.run(VerifyEmailCommand(token="raw"))

    fake_transaction.commit.assert_not_called()
    fake_confirm_events.publish.assert_not_called()
