from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommand,
    SetUserAvatarCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.infrastructure.configs import S3Config


def _make_handler(**kwargs) -> SetUserAvatarCommandHandler:  # noqa: ANN003
    return SetUserAvatarCommandHandler(**kwargs)


async def test_set_avatar_happy_path_uploads_and_attaches(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
    s3_config: S3Config,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = _make_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
        file_storage=fake_file_storage,
        s3_config=s3_config,
    )
    file_id = await handler.run(
        SetUserAvatarCommand(
            user_id=user.oid,
            data=b"binary",
            content_type="image/jpeg",
        )
    )

    assert user.avatar_file_id == file_id
    fake_file_storage.put.assert_awaited_once()
    fake_entity_saver.add_one.assert_called_once()
    fake_transaction.flush.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_set_avatar_replaces_and_soft_deletes_old(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
    s3_config: S3Config,
    user,
    existing_file,
) -> None:
    user.avatar_file_id = existing_file.oid
    fake_user_gateway.with_id.return_value = user
    fake_files_gateway.with_id.return_value = existing_file

    handler = _make_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
        file_storage=fake_file_storage,
        s3_config=s3_config,
    )
    await handler.run(
        SetUserAvatarCommand(user_id=user.oid, data=b"binary", content_type="image/png")
    )

    assert existing_file.is_deleted
    fake_transaction.commit.assert_awaited_once()


async def test_set_avatar_accepts_arbitrary_mime(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
    s3_config: S3Config,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = _make_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
        file_storage=fake_file_storage,
        s3_config=s3_config,
    )
    file_id = await handler.run(
        SetUserAvatarCommand(
            user_id=user.oid,
            data=b"binary",
            content_type="application/pdf",
        )
    )

    assert user.avatar_file_id == file_id
    fake_file_storage.put.assert_awaited_once()


async def test_set_avatar_user_missing_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
    s3_config: S3Config,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = _make_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        files_gateway=fake_files_gateway,
        file_storage=fake_file_storage,
        s3_config=s3_config,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            SetUserAvatarCommand(
                user_id=user.oid,
                data=b"binary",
                content_type="image/jpeg",
            )
        )

    fake_file_storage.put.assert_not_called()
    fake_transaction.commit.assert_not_called()
