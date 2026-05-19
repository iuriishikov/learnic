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
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import CollageItem, PhotoCollageBlock
from learnic.entities.course_block.value_objects import (
    BlockTitle,
    CollageCaption,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID

_IMAGE_CONTENT_TYPE_PREFIX: Final[str] = "image/"


@dataclass(slots=True, frozen=True)
class CollageItemUpload:
    """One photo upload — raw bytes + content-type + optional caption.

    The HTTP layer pairs each multipart ``file`` field with the
    corresponding positional ``caption`` field; order in the
    ``items`` tuple becomes the persisted collage order.
    """

    data: bytes
    content_type: str
    caption: str | None = None


@dataclass(slots=True, frozen=True)
class AddPhotoCollageBlockCommand:
    actor_id: UserID
    lesson_id: CourseLessonID
    items: tuple[CollageItemUpload, ...]
    title: str | None = None


@final
class AddPhotoCollageBlockCommandHandler:
    """Upload all photos in one shot and append a collage block.

    Order of operations mirrors the single-file flow but in aggregate:
    every item is content-type-checked first, then quota is checked
    against the total bytes, then all uploads run, then the block is
    built. A single rejection (content-type or quota) aborts the
    whole batch before any S3 write.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: CourseLessonGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        entitlement: EntitlementService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus

    async def _validate_and_upload(
        self,
        items: tuple[CollageItemUpload, ...],
        actor_id: UserID,
        quota_owner_id: UserID,
    ) -> list[CollageItem]:
        for src in items:
            if not src.content_type.startswith(_IMAGE_CONTENT_TYPE_PREFIX):
                raise WrongFileContentTypeError(
                    file_id="<upload>",
                    expected_prefix=_IMAGE_CONTENT_TYPE_PREFIX,
                    actual=src.content_type,
                )
        total_bytes = sum(len(src.data) for src in items)
        await self._entitlement.ensure_can_upload(
            quota_owner_id,
            total_bytes,
        )

        out: list[CollageItem] = []
        for src in items:
            file = await self._file_uploads.upload(
                src.data,
                src.content_type,
                actor_id,
            )
            caption = (
                CollageCaption(src.caption) if src.caption is not None else None
            )
            out.append(CollageItem(file_id=file.oid, caption=caption))
        return out

    async def run(self, data: AddPhotoCollageBlockCommand) -> LessonBlockID:
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

        items = await self._validate_and_upload(
            data.items,
            actor_id=data.actor_id,
            quota_owner_id=product.author_id,
        )
        title = BlockTitle(data.title) if data.title is not None else None

        existing = await self._block_gateway.list_for_lesson(data.lesson_id)
        next_position = max((b.position for b in existing), default=-1) + 1

        block = PhotoCollageBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            items=items,
            position=next_position,
            title=title,
        )
        await self._block_gateway.add_photo_collage(block)
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
        return block.oid
