from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.user.change_first_name import (
    ChangeUserFirstNameCommand,
    ChangeUserFirstNameCommandHandler,
)
from learnic.application.commands.user.change_last_name import (
    ChangeUserLastNameCommand,
    ChangeUserLastNameCommandHandler,
)
from learnic.application.commands.user.change_patronymic import (
    ChangeUserPatronymicCommand,
    ChangeUserPatronymicCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.user.errors import EmptyNameError
from learnic.entities.user.value_objects import Patronymic


async def test_change_first_name_updates_and_commits(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserFirstNameCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    await handler.run(ChangeUserFirstNameCommand(user_id=user.oid, value="New"))

    assert user.first_name.value == "New"
    fake_transaction.commit.assert_awaited_once()


async def test_change_first_name_user_missing_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = ChangeUserFirstNameCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(ChangeUserFirstNameCommand(user_id=user.oid, value="X"))
    fake_transaction.commit.assert_not_called()


async def test_change_first_name_empty_raises_field_error(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserFirstNameCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    with pytest.raises(EmptyNameError):
        await handler.run(ChangeUserFirstNameCommand(user_id=user.oid, value="   "))
    fake_transaction.commit.assert_not_called()


async def test_change_last_name_updates_and_commits(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserLastNameCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    await handler.run(ChangeUserLastNameCommand(user_id=user.oid, value="Surname"))

    assert user.last_name.value == "Surname"
    fake_transaction.commit.assert_awaited_once()


async def test_change_patronymic_sets_value(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserPatronymicCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    await handler.run(ChangeUserPatronymicCommand(user_id=user.oid, value="Ivanovich"))

    assert user.patronymic == Patronymic("Ivanovich")
    fake_transaction.commit.assert_awaited_once()


async def test_change_patronymic_with_none_clears_value(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    user,
) -> None:
    user.patronymic = Patronymic("Ivanovich")
    fake_user_gateway.with_id.return_value = user

    handler = ChangeUserPatronymicCommandHandler(
        transaction=fake_transaction, user_gateway=fake_user_gateway
    )
    await handler.run(ChangeUserPatronymicCommand(user_id=user.oid, value=None))

    assert user.patronymic is None
    fake_transaction.commit.assert_awaited_once()
