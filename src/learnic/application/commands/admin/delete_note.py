from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesReader
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    DeletedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AdminDeleteNoteCommand:
    actor_id: UserID
    note_id: ProductID


@final
class AdminDeleteNoteCommandHandler:
    """Permanently delete a note regardless of status or ownership.

    The admin-only escalation of :class:`DeleteProductCommandHandler`:
    it drops that handler's author check and DRAFT-only guard so a
    moderator can remove abusive or illegal content even after it has
    been published, archived, and accumulated enrollments.

    **Irreversible.** Deletion cascades at the database level
    (``ON DELETE CASCADE`` on every child FK) to the note's
    modules, lessons, blocks, releases, enrollments, statistics,
    collaborations, roles, gifts, Q&A, tags, and notifications. The
    commercial history of the note is erased. The file-cleanup and
    delete mechanics mirror the author-facing handler; only the
    guard clauses differ.
    """

    def __init__(
        self,
        transaction: Transaction,
        product_gateway: ProductGateway,
        files_reader: FilesReader,
        file_uploads: FileUploadService,
        event_bus: ProductEventBus,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._product_gateway: Final = product_gateway
        self._files_reader: Final = files_reader
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus
        self._quota_publisher: Final = quota_publisher

    async def run(self, data: AdminDeleteNoteCommand) -> None:
        product = await self._product_gateway.with_id(data.note_id)
        if product is None:
            raise EntityNotFoundError(data.note_id)
        product_id = product.oid
        author_id = product.author_id
        # Snapshot every file the note references (cover + file /
        # video / collage block contents) BEFORE the cascade — once
        # the block rows are gone the union-walk returns nothing.
        file_ids = await self._files_reader.file_ids_for_product(
            product_id,
        )
        await self._product_gateway.delete(product)
        for file_id in file_ids:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=DeletedPayload(),
            product_id=product_id,
            actor_id=data.actor_id,
        )
        if file_ids:
            await self._quota_publisher.usage_changed(author_id)
