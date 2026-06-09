"""Unit tests for the file-backed *add* block handlers.

Covers the four upload-and-append handlers that were previously
untested: generic file, uploaded video, photo collage (batch), and
single collage-item append. The focus is the parts unique to these
handlers — the storage-quota gate fires before any S3 write, the
content-type prefix guard rejects mislabelled uploads, and the new
block lands at the next free position.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.note_block.add_file import (
    AddFileBlockCommand,
    AddFileBlockCommandHandler,
)
from learnic.application.commands.note_block.add_photo_collage import (
    AddPhotoCollageBlockCommand,
    AddPhotoCollageBlockCommandHandler,
    CollageItemUpload,
)
from learnic.application.commands.note_block.add_photo_collage_item import (
    AddPhotoCollageItemCommand,
    AddPhotoCollageItemCommandHandler,
)
from learnic.application.commands.note_block.add_video_file import (
    AddVideoFileBlockCommand,
    AddVideoFileBlockCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    StorageQuotaExceededError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.entities.note_block.models import (
    FileBlock,
    HtmlBlock,
    PhotoCollageBlock,
    VideoFileBlock,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID
from tests.unit.application.uploads import FakeUpload

_TWO_GIB = 2 * 1024 * 1024 * 1024


def _quota_error() -> StorageQuotaExceededError:
    return StorageQuotaExceededError(
        plan_code="FREE",
        used_bytes=_TWO_GIB,
        attempted_bytes=1024,
        limit_bytes=_TWO_GIB,
    )


# ---- add_file ----


async def test_add_file_block_uploads_and_appends(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_block_gateway.list_for_lesson.return_value = []

    handler = AddFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    payload = b"%PDF-1.7 fake pdf bytes"
    upload = FakeUpload(content_type="application/pdf", size=len(payload))
    oid = await handler.run(
        AddFileBlockCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            upload=upload,
            title="Slides",
        ),
    )

    fake_entitlement.ensure_can_upload.assert_awaited_once_with(
        note_product.author_id,
        len(payload),
    )
    fake_file_uploads.upload_stream.assert_awaited_once_with(
        upload,
        author_id,
    )
    fake_block_gateway.add_file.assert_awaited_once()
    saved = fake_block_gateway.add_file.call_args.args[0]
    assert isinstance(saved, FileBlock)
    assert saved.oid == oid
    assert saved.position == 0
    assert saved.file_id is not None
    assert saved.title is not None
    assert saved.title.value == "Slides"
    fake_transaction.commit.assert_awaited_once()
    # Adding a file grows the owner's pool — publish a fresh snapshot
    # keyed on the note author, not the acting collaborator.
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )


async def test_add_file_block_appends_after_existing_blocks(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    # html_block is at position 0 → the new file block appends at 1.
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_block_gateway.list_for_lesson.return_value = [html_block]

    handler = AddFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    await handler.run(
        AddFileBlockCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            upload=FakeUpload(content_type="application/zip"),
        ),
    )

    saved = fake_block_gateway.add_file.call_args.args[0]
    assert saved.position == 1


async def test_add_file_block_quota_exceeded_skips_upload(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_entitlement.ensure_can_upload.side_effect = _quota_error()

    handler = AddFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(StorageQuotaExceededError):
        await handler.run(
            AddFileBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                upload=FakeUpload(content_type="application/pdf"),
            ),
        )

    fake_file_uploads.upload_stream.assert_not_called()
    fake_block_gateway.add_file.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_add_file_block_missing_lesson_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = None

    handler = AddFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AddFileBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(uuid.uuid4()),
                upload=FakeUpload(content_type="application/pdf"),
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()


# ---- add_video_file ----


async def test_add_video_file_block_uploads_and_appends(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_block_gateway.list_for_lesson.return_value = []

    handler = AddVideoFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    payload = b"\x00\x00\x00 video bytes"
    oid = await handler.run(
        AddVideoFileBlockCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            upload=FakeUpload(content_type="video/mp4", size=len(payload)),
        ),
    )

    fake_entitlement.ensure_can_upload.assert_awaited_once_with(
        note_product.author_id,
        len(payload),
    )
    fake_file_uploads.upload_stream.assert_awaited_once()
    fake_block_gateway.add_video_file.assert_awaited_once()
    saved = fake_block_gateway.add_video_file.call_args.args[0]
    assert isinstance(saved, VideoFileBlock)
    assert saved.oid == oid
    assert saved.position == 0
    fake_transaction.commit.assert_awaited_once()


async def test_add_video_file_block_rejects_non_video(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    # A non-video content type is rejected BEFORE the quota check and
    # before any S3 write.
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product

    handler = AddVideoFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(WrongFileContentTypeError):
        await handler.run(
            AddVideoFileBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                upload=FakeUpload(content_type="application/pdf"),
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()
    fake_block_gateway.add_video_file.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_add_video_file_block_quota_exceeded_skips_upload(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_entitlement.ensure_can_upload.side_effect = _quota_error()

    handler = AddVideoFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(StorageQuotaExceededError):
        await handler.run(
            AddVideoFileBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                upload=FakeUpload(content_type="video/mp4"),
            ),
        )

    fake_file_uploads.upload_stream.assert_not_called()
    fake_block_gateway.add_video_file.assert_not_called()


# ---- add_photo_collage (batch) ----


async def test_add_photo_collage_uploads_all_and_charges_total(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_block_gateway.list_for_lesson.return_value = []

    handler = AddPhotoCollageBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    items = (
        CollageItemUpload(
            upload=FakeUpload(content_type="image/png", size=100),
        ),
        CollageItemUpload(
            upload=FakeUpload(content_type="image/jpeg", size=200),
            caption="Second",
        ),
    )
    oid = await handler.run(
        AddPhotoCollageBlockCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            items=items,
        ),
    )

    # Quota is charged once for the summed payload, not per-item.
    fake_entitlement.ensure_can_upload.assert_awaited_once_with(
        note_product.author_id,
        300,
    )
    assert fake_file_uploads.upload_stream.await_count == 2
    fake_block_gateway.add_photo_collage.assert_awaited_once()
    saved = fake_block_gateway.add_photo_collage.call_args.args[0]
    assert isinstance(saved, PhotoCollageBlock)
    assert saved.oid == oid
    assert len(saved.items) == 2
    fake_transaction.commit.assert_awaited_once()


async def test_add_photo_collage_rejects_non_image_item(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    # One bad content type aborts the whole batch before any upload
    # or quota charge.
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product

    handler = AddPhotoCollageBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    items = (
        CollageItemUpload(
            upload=FakeUpload(content_type="image/png", size=100),
        ),
        CollageItemUpload(
            upload=FakeUpload(content_type="text/plain", size=200),
        ),
    )
    with pytest.raises(WrongFileContentTypeError):
        await handler.run(
            AddPhotoCollageBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                items=items,
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()
    fake_block_gateway.add_photo_collage.assert_not_called()


async def test_add_photo_collage_quota_exceeded_skips_upload(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_entitlement.ensure_can_upload.side_effect = _quota_error()

    handler = AddPhotoCollageBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    items = (
        CollageItemUpload(
            upload=FakeUpload(content_type="image/png", size=100),
        ),
    )
    with pytest.raises(StorageQuotaExceededError):
        await handler.run(
            AddPhotoCollageBlockCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                items=items,
            ),
        )

    fake_file_uploads.upload_stream.assert_not_called()
    fake_block_gateway.add_photo_collage.assert_not_called()


# ---- add_photo_collage_item (single append to existing collage) ----


async def test_add_photo_collage_item_appends_to_block(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    photo_collage_block: PhotoCollageBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = photo_collage_block
    fake_product_gateway.with_id.return_value = note_product

    handler = AddPhotoCollageItemCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    payload = b"image-bytes"
    item_id = await handler.run(
        AddPhotoCollageItemCommand(
            actor_id=author_id,
            block_id=photo_collage_block.oid,
            upload=FakeUpload(content_type="image/png", size=len(payload)),
            caption="A caption",
        ),
    )

    fake_entitlement.ensure_can_upload.assert_awaited_once_with(
        note_product.author_id,
        len(payload),
    )
    fake_file_uploads.upload_stream.assert_awaited_once()
    fake_block_gateway.add_photo_collage_item.assert_awaited_once()
    saved_block, saved_item = fake_block_gateway.add_photo_collage_item.call_args.args
    assert saved_block is photo_collage_block
    assert saved_item.oid == item_id
    # Started with one item; the append makes two.
    assert len(photo_collage_block.items) == 2
    fake_transaction.commit.assert_awaited_once()
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )


async def test_add_photo_collage_item_wrong_block_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    # Pointing the item-append at a non-collage block fails fast,
    # before touching the quota or storage.
    fake_block_gateway.with_id.return_value = html_block

    handler = AddPhotoCollageItemCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            AddPhotoCollageItemCommand(
                actor_id=author_id,
                block_id=html_block.oid,
                upload=FakeUpload(content_type="image/png"),
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()


async def test_add_photo_collage_item_rejects_non_image(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    photo_collage_block: PhotoCollageBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = photo_collage_block
    fake_product_gateway.with_id.return_value = note_product

    handler = AddPhotoCollageItemCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(WrongFileContentTypeError):
        await handler.run(
            AddPhotoCollageItemCommand(
                actor_id=author_id,
                block_id=photo_collage_block.oid,
                upload=FakeUpload(content_type="application/pdf"),
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()


async def test_add_file_block_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    other_user_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_lessons",
    )

    handler = AddFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddFileBlockCommand(
                actor_id=other_user_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                upload=FakeUpload(content_type="application/pdf"),
            ),
        )

    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_quota_publisher.usage_changed.assert_not_awaited()
