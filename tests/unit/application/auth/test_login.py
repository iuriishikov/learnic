from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.login import (
    LoginCommand,
    LoginCommandHandler,
)
from learnic.application.common.errors import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
)


async def test_login_success_issues_token_pair(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
    verified_user,
) -> None:
    fake_user_gateway.with_email.return_value = verified_user
    fake_hasher.verify.return_value = True

    handler = LoginCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
        notification_publisher=AsyncMock(),
    )
    pair = await handler.run(
        LoginCommand(email="user@example.com", password="correcthorsebattery")
    )

    assert pair.access_token == "jwt"
    assert pair.refresh_token == "raw-refresh"
    fake_refresh_store.issue.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_login_unknown_user_raises_invalid_credentials(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
) -> None:
    fake_user_gateway.with_email.return_value = None

    handler = LoginCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
        notification_publisher=AsyncMock(),
    )
    with pytest.raises(InvalidCredentialsError):
        await handler.run(
            LoginCommand(
                email="unknown@example.com",
                password="correcthorsebattery",
            )
        )
    fake_transaction.commit.assert_not_awaited()


async def test_login_wrong_password_raises_invalid_credentials(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
    verified_user,
) -> None:
    fake_user_gateway.with_email.return_value = verified_user
    fake_hasher.verify.return_value = False

    handler = LoginCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
        notification_publisher=AsyncMock(),
    )
    with pytest.raises(InvalidCredentialsError):
        await handler.run(
            LoginCommand(email="user@example.com", password="wrongpassword00")
        )
    fake_transaction.commit.assert_not_awaited()


async def test_login_unverified_email_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_access_tokens: MagicMock,
    fake_refresh_store: AsyncMock,
    unverified_user,
) -> None:
    fake_user_gateway.with_email.return_value = unverified_user
    fake_hasher.verify.return_value = True

    handler = LoginCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        access_tokens=fake_access_tokens,
        refresh_store=fake_refresh_store,
        notification_publisher=AsyncMock(),
    )
    with pytest.raises(EmailNotVerifiedError):
        await handler.run(
            LoginCommand(email="user@example.com", password="correcthorsebattery")
        )
    fake_transaction.commit.assert_not_awaited()
