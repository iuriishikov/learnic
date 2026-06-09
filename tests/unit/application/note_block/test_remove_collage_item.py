"""Unit tests for ``RemovePhotoCollageItemCommandHandler``.

The handler now fetches the parent product (to source the quota
owner) and publishes a fresh storage-quota snapshot keyed on the
note author — but only when the removal actually frees a backing
file. A placeholder item with no ``file_id`` frees nothing, so the
publish is skipped.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.note_block.remove_photo_collage_item import (  # noqa: E501
    RemovePhotoCollageItemCommand,
    RemovePhotoCollageItemCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.entities.note_block.ids import CollageItemID
from learnic.entities.note_block.models import (
    CollageItem,
    HtmlBlock,
    PhotoCollageBlock,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.file.ids import FileID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


def _two_item_collage(
    note_lesson: NoteLesson,
    *,
    second_has_file: bool,
) -> PhotoCollageBlock:
    second_file = (
        FileID(uuid.uuid4()) if second_has_file else None
    )
    return PhotoCollageBlock.create(
        lesson_id=NoteLessonID(note_lesson.oid),
        product_id=note_lesson.product_id,
        items=[
            CollageItem(
                oid=CollageItemID(uuid.uuid4()),
                file_id=FileID(uuid.uuid4()),
            ),
            CollageItem(
                oid=CollageItemID(uuid.uuid4()),
                file_id=second_file,
            ),
        ],
        position=0,
    )


def _build_handler(
    *,
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
) -> RemovePhotoCollageItemCommandHandler:
    return RemovePhotoCollageItemCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )


async def test_remove_collage_item_publishes_when_file_freed(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    block = _two_item_collage(note_lesson, second_has_file=True)
    freed_id = block.items[1].file_id
    fake_block_gateway.with_id.return_value = block
    fake_product_gateway.with_id.return_value = note_product

    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_block_gateway=fake_block_gateway,
        fake_file_uploads=fake_file_uploads,
        fake_event_bus=fake_event_bus,
        fake_quota_publisher=fake_quota_publisher,
    )
    await handler.run(
        RemovePhotoCollageItemCommand(
            actor_id=author_id,
            block_id=block.oid,
            item_id=block.items[1].oid,
        ),
    )

    fake_file_uploads.soft_delete_previous.assert_awaited_once_with(
        freed_id,
    )
    fake_transaction.commit.assert_awaited_once()
    # The freed file shrinks the owner's pool — publish on the author.
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )


async def test_remove_collage_item_skips_publish_for_placeholder(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    # The removed item carries no backing file → nothing is freed,
    # so neither the S3 purge nor the quota publish should fire.
    block = _two_item_collage(note_lesson, second_has_file=False)
    fake_block_gateway.with_id.return_value = block
    fake_product_gateway.with_id.return_value = note_product

    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_block_gateway=fake_block_gateway,
        fake_file_uploads=fake_file_uploads,
        fake_event_bus=fake_event_bus,
        fake_quota_publisher=fake_quota_publisher,
    )
    await handler.run(
        RemovePhotoCollageItemCommand(
            actor_id=author_id,
            block_id=block.oid,
            item_id=block.items[1].oid,
        ),
    )

    fake_file_uploads.soft_delete_previous.assert_not_called()
    fake_transaction.commit.assert_awaited_once()
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_remove_collage_item_missing_product_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    block = _two_item_collage(note_lesson, second_has_file=True)
    fake_block_gateway.with_id.return_value = block
    fake_product_gateway.with_id.return_value = None

    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_block_gateway=fake_block_gateway,
        fake_file_uploads=fake_file_uploads,
        fake_event_bus=fake_event_bus,
        fake_quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RemovePhotoCollageItemCommand(
                actor_id=author_id,
                block_id=block.oid,
                item_id=block.items[1].oid,
            ),
        )

    fake_authorizer.require.assert_not_called()
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_remove_collage_item_wrong_block_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block

    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_block_gateway=fake_block_gateway,
        fake_file_uploads=fake_file_uploads,
        fake_event_bus=fake_event_bus,
        fake_quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            RemovePhotoCollageItemCommand(
                actor_id=author_id,
                block_id=html_block.oid,
                item_id=CollageItemID(uuid.uuid4()),
            ),
        )

    fake_product_gateway.with_id.assert_not_called()
    fake_quota_publisher.usage_changed.assert_not_awaited()
