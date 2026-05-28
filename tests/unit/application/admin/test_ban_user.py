import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.admin.ban_user import (
    BanUserCommand,
    BanUserCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.user.models import User, UserID
from learnic.infrastructure.configs import SecurityConfig


def _handler(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config: SecurityConfig,
) -> BanUserCommandHandler:
    return BanUserCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        refresh_store=fake_refresh_store,
        denylist=fake_denylist,
        security_config=security_config,
    )


async def test_ban_sets_flag_revokes_sessions_and_denies_families(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config: SecurityConfig,
    regular_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = regular_user
    family_id = uuid.uuid4()
    fake_refresh_store.revoke_all_for_user.return_value = {family_id}

    handler = _handler(
        fake_transaction,
        fake_user_gateway,
        fake_refresh_store,
        fake_denylist,
        security_config,
    )
    await handler.run(BanUserCommand(user_id=regular_user.oid))

    assert regular_user.is_banned is True
    fake_refresh_store.revoke_all_for_user.assert_awaited_once_with(
        regular_user.oid,
    )
    fake_denylist.deny_family.assert_awaited_once()
    assert fake_denylist.deny_family.await_args.args[0] == family_id
    fake_transaction.commit.assert_awaited_once()


async def test_ban_with_no_active_sessions_skips_denylist(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config: SecurityConfig,
    regular_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = regular_user
    fake_refresh_store.revoke_all_for_user.return_value = set()

    handler = _handler(
        fake_transaction,
        fake_user_gateway,
        fake_refresh_store,
        fake_denylist,
        security_config,
    )
    await handler.run(BanUserCommand(user_id=regular_user.oid))

    assert regular_user.is_banned is True
    fake_denylist.deny_family.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_ban_unknown_user_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_refresh_store: AsyncMock,
    fake_denylist: AsyncMock,
    security_config: SecurityConfig,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = _handler(
        fake_transaction,
        fake_user_gateway,
        fake_refresh_store,
        fake_denylist,
        security_config,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(BanUserCommand(user_id=UserID(uuid.uuid4())))
    fake_refresh_store.revoke_all_for_user.assert_not_awaited()
    fake_transaction.commit.assert_not_awaited()
