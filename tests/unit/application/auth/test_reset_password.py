from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.reset_password import (
    ResetPasswordCommand,
    ResetPasswordCommandHandler,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.email_tokens import EmailTokenPurpose
from learnic.entities.user.value_objects import PasswordHash


async def test_reset_password_sets_new_hash_and_revokes_sessions(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_email_tokens: AsyncMock,
    fake_hasher: MagicMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config,
    verified_user,
) -> None:
    fake_email_tokens.consume.return_value = verified_user.oid
    fake_user_gateway.with_id.return_value = verified_user
    fake_hasher.hash.return_value = PasswordHash("new-hash")
    fake_refresh_store.revoke_all_for_user.return_value = set()

    handler = ResetPasswordCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        email_tokens=fake_email_tokens,
        hasher=fake_hasher,
        refresh_store=fake_refresh_store,
        denylist=fake_denylist,
        security_config=security_config,
    )
    await handler.run(ResetPasswordCommand(token="raw", new_password="newcorrecthorse"))

    fake_email_tokens.consume.assert_awaited_once_with("raw", EmailTokenPurpose.RESET)
    assert verified_user.password_hash.value == "new-hash"
    fake_refresh_store.revoke_all_for_user.assert_awaited_once_with(verified_user.oid)
    fake_transaction.commit.assert_awaited_once()


async def test_reset_password_missing_user_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_email_tokens: AsyncMock,
    fake_hasher: MagicMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config,
    verified_user,
) -> None:
    fake_email_tokens.consume.return_value = verified_user.oid
    fake_user_gateway.with_id.return_value = None

    handler = ResetPasswordCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        email_tokens=fake_email_tokens,
        hasher=fake_hasher,
        refresh_store=fake_refresh_store,
        denylist=fake_denylist,
        security_config=security_config,
    )
    with pytest.raises(InvalidTokenError):
        await handler.run(
            ResetPasswordCommand(token="raw", new_password="newcorrecthorse")
        )

    fake_transaction.commit.assert_not_called()
