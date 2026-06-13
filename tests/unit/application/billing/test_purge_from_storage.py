"""Unit tests for ``PurgeFileFromStorageCommandHandler``.

The task body is small but load-bearing: it owns the
"schedule then rollback" safety contract (live row → no-op), the
S3 / collage / row order of operations, and the idempotency
guarantees for retried tasks.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from learnic.application.commands.file.purge_from_storage import (
    PurgeFileFromStorageCommand,
    PurgeFileFromStorageCommandHandler,
)
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.user.models import UserID


def _make_file(*, deleted: bool) -> File:
    oid = FileID(uuid.uuid4())
    file = File(
        oid=oid,
        storage_name=StorageName(str(oid)),
        bucket=StorageBucket("learnic-test"),
        content_type=ContentType("image/png"),
        size_bytes=FileSize(1024),
        uploaded_by=UserID(uuid.uuid4()),
        uploaded_at=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    return file


def _build_handler(
    *,
    transaction: AsyncMock,
    files_gateway: AsyncMock,
    block_gateway: AsyncMock,
    file_storage: AsyncMock,
    task_scheduler: AsyncMock | None = None,
) -> PurgeFileFromStorageCommandHandler:
    return PurgeFileFromStorageCommandHandler(
        transaction=transaction,
        files_gateway=files_gateway,
        block_gateway=block_gateway,
        file_storage=file_storage,
        task_scheduler=task_scheduler or AsyncMock(),
    )


async def test_missing_row_is_no_op(
    fake_transaction: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Producer's transaction rolled back AFTER scheduling the task,
    # so the row was never committed. Worker must NOT touch S3.
    fake_files_gateway.with_id.return_value = None
    handler = _build_handler(
        transaction=fake_transaction,
        files_gateway=fake_files_gateway,
        block_gateway=fake_block_gateway,
        file_storage=fake_file_storage,
    )

    await handler.run(PurgeFileFromStorageCommand(file_id=FileID(uuid.uuid4())))

    fake_file_storage.delete.assert_not_called()
    fake_block_gateway.remove_file_from_collages.assert_not_called()
    fake_files_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_live_row_is_no_op_rollback_safety(
    fake_transaction: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Producer scheduled the task, then transaction rolled back —
    # ``mark_deleted`` mutation was reverted, the row is alive
    # again. Worker must abort.
    fake_files_gateway.with_id.return_value = _make_file(deleted=False)
    handler = _build_handler(
        transaction=fake_transaction,
        files_gateway=fake_files_gateway,
        block_gateway=fake_block_gateway,
        file_storage=fake_file_storage,
    )

    await handler.run(PurgeFileFromStorageCommand(file_id=FileID(uuid.uuid4())))

    fake_file_storage.delete.assert_not_called()
    fake_files_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_soft_deleted_row_purges_everywhere(
    fake_transaction: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Happy path: producer committed, row is ``deleted_at != NULL``.
    # Worker erases S3 blob → excises file from collages → drops the
    # row → commits.
    file = _make_file(deleted=True)
    fake_files_gateway.with_id.return_value = file
    handler = _build_handler(
        transaction=fake_transaction,
        files_gateway=fake_files_gateway,
        block_gateway=fake_block_gateway,
        file_storage=fake_file_storage,
    )
    cmd = PurgeFileFromStorageCommand(file_id=file.oid)

    await handler.run(cmd)

    fake_file_storage.delete.assert_called_once_with(
        bucket=file.bucket.value,
        name=file.storage_name.value,
    )
    fake_block_gateway.remove_file_from_collages.assert_called_once_with(
        file.oid,
    )
    fake_files_gateway.delete.assert_called_once_with(file.oid)
    fake_transaction.commit.assert_called_once()


async def test_release_pinned_file_is_not_purged(
    fake_transaction: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # Row is soft-deleted, but a published-release snapshot still
    # points at this exact blob (releases share the file, they do not
    # copy it). The worker must abort rather than strip media out of
    # already-published content.
    file = _make_file(deleted=True)
    fake_files_gateway.with_id.return_value = file
    fake_files_gateway.is_referenced_by_release.return_value = True
    handler = _build_handler(
        transaction=fake_transaction,
        files_gateway=fake_files_gateway,
        block_gateway=fake_block_gateway,
        file_storage=fake_file_storage,
    )

    await handler.run(PurgeFileFromStorageCommand(file_id=file.oid))

    fake_files_gateway.is_referenced_by_release.assert_awaited_once_with(
        file.oid,
    )
    fake_file_storage.delete.assert_not_called()
    fake_block_gateway.remove_file_from_collages.assert_not_called()
    fake_files_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_purge_order_s3_then_collages_then_row(
    fake_transaction: AsyncMock,
    fake_files_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_file_storage: AsyncMock,
) -> None:
    # If the row dropped before the collage UPDATE, the JSONB
    # ``@>`` predicate would still match (it works on the array
    # contents, not on the files FK), but if anything in the
    # future starts joining on ``files`` the order matters.
    # Lock it in with a test.
    file = _make_file(deleted=True)
    fake_files_gateway.with_id.return_value = file
    order: list[str] = []
    fake_file_storage.delete.side_effect = (
        lambda **_: order.append("s3")
    )
    fake_block_gateway.remove_file_from_collages.side_effect = (
        lambda _: order.append("collages")
    )
    fake_files_gateway.delete.side_effect = lambda _: order.append("row")
    handler = _build_handler(
        transaction=fake_transaction,
        files_gateway=fake_files_gateway,
        block_gateway=fake_block_gateway,
        file_storage=fake_file_storage,
    )

    await handler.run(PurgeFileFromStorageCommand(file_id=file.oid))

    assert order == ["s3", "collages", "row"]
