from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.errors import CollageItemsMismatchError
from learnic.entities.course_block.ids import CollageItemID, LessonBlockID
from learnic.entities.course_block.models import PhotoCollageBlock
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RemovePhotoCollageItemCommand:
    """Delete one photo from a collage by item id.

    Raises :class:`TooFewCollageItemsError` (HTTP 422) if the removal
    would push the count below ``PHOTO_COLLAGE_MIN_ITEMS`` — the
    block must always carry at least one item. Use
    :class:`DeleteLessonBlockCommand` to remove the whole block.
    """

    actor_id: UserID
    block_id: LessonBlockID
    item_id: CollageItemID


@final
class RemovePhotoCollageItemCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus

    async def run(self, data: RemovePhotoCollageItemCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, PhotoCollageBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.PHOTO_COLLAGE.value,
                actual=block.type.value,
            )
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(block.product_id),
            Permission.EDIT_LESSONS,
        )

        try:
            freed_file_id = block.remove_item(data.item_id)
        except CollageItemsMismatchError as exc:
            raise EntityNotFoundError(data.item_id) from exc
        await self._block_gateway.remove_photo_collage_item(
            block,
            data.item_id,
        )
        if freed_file_id is not None:
            await self._file_uploads.soft_delete_previous(freed_file_id)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
