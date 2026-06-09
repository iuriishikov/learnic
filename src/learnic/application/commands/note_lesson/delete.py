from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    LessonDeletedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.file import FilesReader
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteNoteLessonCommand:
    actor_id: UserID
    lesson_id: NoteLessonID


@final
class DeleteNoteLessonCommandHandler:
    """Hard-delete a lesson. Cascades to its blocks via FK.

    The cascade silently drops file / video-file / collage block
    rows, so the files they referenced are snapshotted BEFORE the
    delete and soft-deleted alongside it — otherwise the rows
    would linger live (quota-invisible) and the S3 blobs would
    orphan forever. Same sweep discipline as block-level and
    product-level deletes.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        files_reader: FilesReader,
        file_uploads: FileUploadService,
        event_bus: ContentEventBus,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._files_reader: Final = files_reader
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus
        self._quota_publisher: Final = quota_publisher

    async def run(self, data: DeleteNoteLessonCommand) -> None:
        lesson = await self._lesson_gateway.with_id(data.lesson_id)
        if lesson is None:
            raise EntityNotFoundError(data.lesson_id)
        product = await self._product_gateway.with_id(lesson.product_id)
        if product is None:
            raise EntityNotFoundError(lesson.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(lesson.product_id),
            Permission.EDIT_LESSONS,
        )
        product_id = lesson.product_id
        # Snapshot the lesson's file references BEFORE the cascade —
        # afterwards the block rows are gone and the union-walk
        # would return nothing.
        file_ids = await self._files_reader.file_ids_for_lesson(
            data.lesson_id,
        )
        await self._lesson_gateway.delete(lesson)
        for file_id in file_ids:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=LessonDeletedPayload(lesson_id=str(data.lesson_id)),
            product_id=product_id,
            actor_id=data.actor_id,
        )
        if file_ids:
            await self._quota_publisher.usage_changed(product.author_id)
