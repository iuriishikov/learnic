"""Quota wiring for replace-semantic file/video-file block updates.

These handlers must credit the bytes freed by the file they replace,
otherwise a same-size (or smaller) swap is double-counted against the
owner's cap and falsely rejected with 413 once the owner is near the
limit. The fix routes them through
:meth:`EntitlementService.ensure_can_replace_upload` (delta-aware)
instead of the pure-add :meth:`ensure_can_upload`, sourcing
``freed_bytes`` from :meth:`FileUploadService.previous_file_size`.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


from learnic.application.commands.note_block.update_file import (
    UpdateFileBlockCommand,
    UpdateFileBlockCommandHandler,
)
from learnic.application.commands.note_block.update_video_file import (
    UpdateVideoFileBlockCommand,
    UpdateVideoFileBlockCommandHandler,
)
from learnic.application.common.storage.file_uploads import (
    DefaultStorageBucket,
    FileUploadService,
)
from learnic.entities.note_block.models import FileBlock, VideoFileBlock
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID
from tests.unit.application.uploads import FakeUpload


def _make_file(size: int, *, deleted: bool) -> File:
    return File(
        oid=FileID(uuid.uuid4()),
        storage_name=StorageName(str(uuid.uuid4())),
        bucket=StorageBucket("test-bucket"),
        content_type=ContentType("application/pdf"),
        size_bytes=FileSize(size),
        uploaded_by=UserID(uuid.uuid4()),
        uploaded_at=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


def _make_upload_service(
    files_gateway: AsyncMock,
    task_scheduler: AsyncMock | None = None,
) -> FileUploadService:
    return FileUploadService(
        transaction=AsyncMock(),
        entity_saver=MagicMock(),
        file_storage=AsyncMock(),
        files_gateway=files_gateway,
        task_scheduler=task_scheduler or AsyncMock(),
        default_bucket=DefaultStorageBucket("test-bucket"),
    )


# ---- FileUploadService.previous_file_size ---- #


async def test_previous_file_size_returns_zero_for_none_id() -> None:
    files_gateway = AsyncMock()
    service = _make_upload_service(files_gateway)

    assert await service.previous_file_size(None) == 0
    files_gateway.with_id.assert_not_called()


async def test_previous_file_size_returns_zero_when_missing() -> None:
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = None
    service = _make_upload_service(files_gateway)

    assert await service.previous_file_size(FileID(uuid.uuid4())) == 0


async def test_previous_file_size_returns_zero_when_soft_deleted() -> None:
    # A soft-deleted file is not in current usage, so replacing it
    # frees nothing the quota aggregate was counting.
    deleted = _make_file(4096, deleted=True)
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = deleted
    service = _make_upload_service(files_gateway)

    assert await service.previous_file_size(deleted.oid) == 0


async def test_previous_file_size_returns_size_for_live_file() -> None:
    live = _make_file(4096, deleted=False)
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = live
    service = _make_upload_service(files_gateway)

    assert await service.previous_file_size(live.oid) == 4096


# ---- FileUploadService.soft_delete_previous release guard ---- #


async def test_soft_delete_previous_purges_unpinned_file() -> None:
    # No release pins it: mark the row deleted, queue the S3 purge,
    # and report the eviction so the caller can credit freed bytes.
    live = _make_file(4096, deleted=False)
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = live
    files_gateway.is_referenced_by_release.return_value = False
    task_scheduler = AsyncMock()
    service = _make_upload_service(files_gateway, task_scheduler)

    evicted = await service.soft_delete_previous(live.oid)

    assert evicted is True
    assert live.is_deleted
    schedule = task_scheduler.schedule_purge_file_from_storage
    # Not release-pinned → purge with force_release_pinned=False.
    schedule.assert_awaited_once_with(live.oid, force_release_pinned=False)


async def test_soft_delete_previous_keeps_release_pinned_file() -> None:
    # A published release still pins this exact blob — releases share
    # the file, they do not copy it. The file must stay fully intact,
    # not even soft-deleted, so it remains visible to release reads and
    # the quota aggregate; the caller is told nothing was evicted.
    live = _make_file(4096, deleted=False)
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = live
    files_gateway.is_referenced_by_release.return_value = True
    task_scheduler = AsyncMock()
    service = _make_upload_service(files_gateway, task_scheduler)

    evicted = await service.soft_delete_previous(live.oid)

    assert evicted is False
    assert not live.is_deleted
    files_gateway.is_referenced_by_release.assert_awaited_once_with(live.oid)
    schedule = task_scheduler.schedule_purge_file_from_storage
    schedule.assert_not_called()


async def test_soft_delete_previous_evicts_release_pinned_when_forced() -> None:
    # Over-quota enforcement passes evict_release_pinned=True: a
    # release-pinned file IS soft-deleted and queued for purge with
    # force_release_pinned=True (quota wins over release immutability),
    # so the worker's own release re-check does not veto the delete.
    live = _make_file(4096, deleted=False)
    files_gateway = AsyncMock()
    files_gateway.with_id.return_value = live
    files_gateway.is_referenced_by_release.return_value = True
    task_scheduler = AsyncMock()
    service = _make_upload_service(files_gateway, task_scheduler)

    evicted = await service.soft_delete_previous(
        live.oid,
        evict_release_pinned=True,
    )

    assert evicted is True
    assert live.is_deleted
    schedule = task_scheduler.schedule_purge_file_from_storage
    schedule.assert_awaited_once_with(live.oid, force_release_pinned=True)


# ---- handler wiring (fixtures: fake_file_uploads, fake_entitlement,
# file_block, video_file_block — shared via conftest.py) ---- #


async def test_update_file_block_credits_freed_bytes_on_replace(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    file_block: FileBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = file_block
    fake_product_gateway.with_id.return_value = note_product
    fake_file_uploads.previous_file_size.return_value = 7777
    # update_file mutates block.file_id, so capture the old id first.
    previous_id = file_block.file_id

    handler = UpdateFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    payload = b"replacement-bytes"
    upload = FakeUpload(content_type="application/pdf", size=len(payload))
    await handler.run(
        UpdateFileBlockCommand(
            actor_id=author_id,
            block_id=file_block.oid,
            upload=upload,
            title=None,
        ),
    )

    fake_file_uploads.previous_file_size.assert_awaited_once_with(
        previous_id,
    )
    fake_entitlement.ensure_can_replace_upload.assert_awaited_once_with(
        note_product.author_id,
        added_bytes=len(payload),
        freed_bytes=7777,
    )
    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.upload_stream.assert_awaited_once()
    fake_file_uploads.soft_delete_previous.assert_awaited_once_with(
        previous_id,
    )
    fake_transaction.commit.assert_awaited_once()
    # Replacing the backing file changes the owner's usage — publish.
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )


async def test_update_file_block_title_only_skips_quota(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    file_block: FileBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = file_block
    fake_product_gateway.with_id.return_value = note_product

    handler = UpdateFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    await handler.run(
        UpdateFileBlockCommand(
            actor_id=author_id,
            block_id=file_block.oid,
            upload=None,
            title="New caption",
        ),
    )

    fake_entitlement.ensure_can_replace_upload.assert_not_called()
    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_file_uploads.previous_file_size.assert_not_called()
    fake_file_uploads.upload_stream.assert_not_called()
    fake_transaction.commit.assert_awaited_once()
    # A title-only edit frees / consumes no storage — no publish.
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_update_video_file_block_credits_freed_bytes_on_replace(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_uploads: MagicMock,
    fake_entitlement: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    video_file_block: VideoFileBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = video_file_block
    fake_product_gateway.with_id.return_value = note_product
    fake_file_uploads.previous_file_size.return_value = 123456
    previous_id = video_file_block.file_id

    handler = UpdateVideoFileBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        file_uploads=fake_file_uploads,
        entitlement=fake_entitlement,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    payload = b"\x00\x01\x02 video bytes"
    upload = FakeUpload(content_type="video/mp4", size=len(payload))
    await handler.run(
        UpdateVideoFileBlockCommand(
            actor_id=author_id,
            block_id=video_file_block.oid,
            upload=upload,
            title=None,
        ),
    )

    fake_file_uploads.previous_file_size.assert_awaited_once_with(
        previous_id,
    )
    fake_entitlement.ensure_can_replace_upload.assert_awaited_once_with(
        note_product.author_id,
        added_bytes=len(payload),
        freed_bytes=123456,
    )
    fake_entitlement.ensure_can_upload.assert_not_called()
    fake_transaction.commit.assert_awaited_once()
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )
