from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import CollageItemID, LessonBlockID
from learnic.entities.note_block.models import PhotoCollageBlock
from learnic.entities.note_block.value_objects import CollageCaption
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID

_IMAGE_CONTENT_TYPE_PREFIX: Final[str] = "image/"


@dataclass(slots=True, frozen=True)
class AddPhotoCollageItemCommand:
    """Append one photo to an existing collage.

    ``upload`` is the streamed incoming upload; its
    ``content_type`` (the client-declared mime) is validated against
    ``image/`` here, then enforced server-side via the file row, and
    its ``size`` is metered for quota. ``caption`` is optional
    (None == no caption). The returned :class:`CollageItemID` is the
    stable identity the SPA uses for subsequent per-item operations.
    """

    actor_id: UserID
    block_id: LessonBlockID
    upload: IncomingUpload
    caption: str | None = None


@final
class AddPhotoCollageItemCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        entitlement: EntitlementService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus

    async def run(self, data: AddPhotoCollageItemCommand) -> CollageItemID:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, PhotoCollageBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.PHOTO_COLLAGE.value,
                actual=block.type.value,
            )
        product = await self._product_gateway.with_id(block.product_id)
        if product is None:
            raise EntityNotFoundError(block.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(block.product_id),
            Permission.EDIT_LESSONS,
        )

        if not data.upload.content_type.startswith(
            _IMAGE_CONTENT_TYPE_PREFIX,
        ):
            raise WrongFileContentTypeError(
                file_id="<upload>",
                expected_prefix=_IMAGE_CONTENT_TYPE_PREFIX,
                actual=data.upload.content_type,
            )

        await self._entitlement.ensure_can_upload(
            product.author_id,
            data.upload.size,
        )

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.actor_id,
        )
        caption = (
            CollageCaption(data.caption) if data.caption is not None else None
        )
        item = block.add_item(file_id=file.oid, caption=caption)
        await self._block_gateway.add_photo_collage_item(block, item)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
        return item.oid
