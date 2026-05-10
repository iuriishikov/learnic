from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommand,
    SetUserAvatarCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError


def _make_handler(**kwargs) -> SetUserAvatarCommandHandler:  # noqa: ANN003
    return SetUserAvatarCommandHandler(**kwargs)


async def test_set_avatar_happy_path_uploads_and_attaches(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = _make_handler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        file_uploads=fake_file_uploads,
    )
    file_id = await handler.run(
        SetUserAvatarCommand(
            user_id=user.oid,
            data=b"binary",
            content_type="image/jpeg",
        )
    )

    assert user.avatar_file_id == file_id
    fake_file_uploads.upload.assert_awaited_once()
    fake_file_uploads.soft_delete_previous.assert_awaited_once_with(None)
    fake_transaction.commit.assert_awaited_once()


async def test_set_avatar_replaces_and_soft_deletes_old(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    user,
    existing_file,
) -> None:
    user.avatar_file_id = existing_file.oid
    fake_user_gateway.with_id.return_value = user

    handler = _make_handler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        file_uploads=fake_file_uploads,
    )
    await handler.run(
        SetUserAvatarCommand(user_id=user.oid, data=b"binary", content_type="image/png")
    )

    fake_file_uploads.soft_delete_previous.assert_awaited_once_with(existing_file.oid)
    fake_transaction.commit.assert_awaited_once()


async def test_set_avatar_accepts_arbitrary_mime(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = user

    handler = _make_handler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        file_uploads=fake_file_uploads,
    )
    file_id = await handler.run(
        SetUserAvatarCommand(
            user_id=user.oid,
            data=b"binary",
            content_type="application/pdf",
        )
    )

    assert user.avatar_file_id == file_id
    fake_file_uploads.upload.assert_awaited_once()


async def test_set_avatar_user_missing_raises(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    user,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = _make_handler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        file_uploads=fake_file_uploads,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            SetUserAvatarCommand(
                user_id=user.oid,
                data=b"binary",
                content_type="image/jpeg",
            )
        )

    fake_file_uploads.upload.assert_not_called()
    fake_transaction.commit.assert_not_called()
