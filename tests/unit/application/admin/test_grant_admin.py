import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.admin.grant_admin import (
    GrantAdminCommand,
    GrantAdminCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.user.models import User, UserID


async def test_grant_admin_sets_flag_and_commits(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    regular_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = regular_user

    handler = GrantAdminCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
    )
    await handler.run(GrantAdminCommand(user_id=regular_user.oid))

    assert regular_user.is_admin is True
    fake_transaction.commit.assert_awaited_once()


async def test_grant_admin_unknown_user_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = GrantAdminCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GrantAdminCommand(user_id=UserID(uuid.uuid4())),
        )
    fake_transaction.commit.assert_not_awaited()
