from unittest.mock import AsyncMock

from learnic.application.commands.user.avatar.remove import (
    RemoveUserAvatarCommand,
    RemoveUserAvatarCommandHandler,
)


async def test_remove_avatar_soft_deletes_existing(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    user,
    existing_file,
) -> None:
    user.avatar_file_id = existing_file.oid
    fake_user_gateway.with_id.return_value = user
    fake_files_gateway.with_id.return_value = existing_file

    handler = RemoveUserAvatarCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
    )
    await handler.run(RemoveUserAvatarCommand(user_id=user.oid))

    assert user.avatar_file_id is None
    assert existing_file.is_deleted
    fake_transaction.commit.assert_awaited_once()


async def test_remove_avatar_without_avatar_is_noop(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = RemoveUserAvatarCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
    )
    await handler.run(RemoveUserAvatarCommand(user_id=user.oid))

    fake_files_gateway.with_id.assert_not_called()
    fake_transaction.commit.assert_awaited_once()
