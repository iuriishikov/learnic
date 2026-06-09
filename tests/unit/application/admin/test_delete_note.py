import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.admin.delete_note import (
    AdminDeleteNoteCommand,
    AdminDeleteNoteCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


def _handler(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
) -> AdminDeleteNoteCommandHandler:
    return AdminDeleteNoteCommandHandler(
        transaction=fake_transaction,
        product_gateway=fake_product_gateway,
        files_reader=fake_files_reader,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )


async def test_delete_note_cascades_files_commits_and_publishes(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_product: MagicMock,
) -> None:
    author_id = UserID(uuid.uuid4())
    fake_product.author_id = author_id
    fake_product_gateway.with_id.return_value = fake_product
    file_id = FileID(uuid.uuid4())
    fake_files_reader.file_ids_for_product.return_value = [file_id]
    fake_quota_publisher = AsyncMock()

    handler = _handler(
        fake_transaction,
        fake_product_gateway,
        fake_files_reader,
        fake_file_uploads,
        fake_event_bus,
        fake_quota_publisher,
    )
    await handler.run(
        AdminDeleteNoteCommand(
            actor_id=UserID(uuid.uuid4()),
            note_id=ProductID(fake_product.oid),
        ),
    )

    fake_product_gateway.delete.assert_awaited_once_with(fake_product)
    fake_file_uploads.soft_delete_previous.assert_awaited_once_with(file_id)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    # Quota is published once, AFTER commit, keyed by the note author —
    # never the acting admin.
    fake_quota_publisher.usage_changed.assert_awaited_once_with(author_id)


async def test_delete_note_without_files_does_not_publish_quota(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_product: MagicMock,
) -> None:
    fake_product.author_id = UserID(uuid.uuid4())
    fake_product_gateway.with_id.return_value = fake_product
    fake_files_reader.file_ids_for_product.return_value = []
    fake_quota_publisher = AsyncMock()

    handler = _handler(
        fake_transaction,
        fake_product_gateway,
        fake_files_reader,
        fake_file_uploads,
        fake_event_bus,
        fake_quota_publisher,
    )
    await handler.run(
        AdminDeleteNoteCommand(
            actor_id=UserID(uuid.uuid4()),
            note_id=ProductID(fake_product.oid),
        ),
    )

    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_delete_note_unknown_raises_and_does_not_commit(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
) -> None:
    fake_product_gateway.with_id.return_value = None
    fake_quota_publisher = AsyncMock()

    handler = _handler(
        fake_transaction,
        fake_product_gateway,
        fake_files_reader,
        fake_file_uploads,
        fake_event_bus,
        fake_quota_publisher,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AdminDeleteNoteCommand(
                actor_id=UserID(uuid.uuid4()),
                note_id=ProductID(uuid.uuid4()),
            ),
        )
    fake_product_gateway.delete.assert_not_awaited()
    fake_transaction.commit.assert_not_awaited()
    fake_event_bus.publish.assert_not_awaited()
    fake_quota_publisher.usage_changed.assert_not_awaited()
