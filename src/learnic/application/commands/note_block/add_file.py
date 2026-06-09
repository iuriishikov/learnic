from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockAddedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import FileBlock
from learnic.entities.note_block.value_objects import BlockTitle
from learnic.entities.common.limits import LESSON_BLOCK_LIMIT
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddFileBlockCommand:
    """Author uploads a single file in one shot and gets a block back.

    ``upload`` is the streamed multipart upload opened at the HTTP
    boundary; its ``content_type`` is whatever the client declared
    (the value is wrapped in a VO on upload) and its bytes are read
    via ``stream(...)``. No content-type prefix check for the generic
    file slot — the typed siblings (video-file, photo-collage) own
    that.
    """

    actor_id: UserID
    lesson_id: NoteLessonID
    upload: IncomingUpload
    title: str | None = None


@final
class AddFileBlockCommandHandler:
    """Persist the uploaded bytes, then append a file-block to the lesson.

    Order of operations is deliberate:

    1. Authorise on the parent note (cheapest reject).
    2. Quota check on ``upload.size`` BEFORE uploading to S3 — failing
       past this point would waste a storage round-trip.
    3. Hand the upload to :class:`FileUploadService`, which streams it
       into the ``File`` row + object storage; the storage write
       happens inside the request transaction (rolled-back blobs are
       swept by the file-lifecycle worker — same as cover/avatar).
    4. Build and persist the block.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        entitlement: EntitlementService,
        event_bus: ContentEventBus,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus
        self._quota_publisher: Final = quota_publisher

    async def run(self, data: AddFileBlockCommand) -> LessonBlockID:
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

        await self._entitlement.ensure_can_upload(
            product.author_id,
            data.upload.size,
        )

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.actor_id,
        )

        title = BlockTitle(data.title) if data.title is not None else None
        await self._block_gateway.lock_for_lesson(data.lesson_id)
        existing = await self._block_gateway.list_for_lesson(data.lesson_id)
        LESSON_BLOCK_LIMIT.ensure(len(existing))
        next_position = max((b.position for b in existing), default=-1) + 1

        block = FileBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            file_id=file.oid,
            position=next_position,
            title=title,
        )
        await self._block_gateway.add_file(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockAddedPayload.from_entity(
                lesson_id=data.lesson_id,
                block=block,
            ),
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
        await self._quota_publisher.usage_changed(product.author_id)
        return block.oid
