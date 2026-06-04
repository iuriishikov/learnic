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
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import CollageItemID, LessonBlockID
from learnic.entities.note_block.models import PhotoCollageBlock
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ReorderPhotoCollageItemsCommand:
    """Reorder photos within a collage.

    ``ordered_ids`` must be a permutation of the block's current item
    ids — anything else raises :class:`CollageItemsMismatchError`
    (HTTP 422). Add/remove flows have their own dedicated commands.
    """

    actor_id: UserID
    block_id: LessonBlockID
    ordered_ids: tuple[CollageItemID, ...]


@final
class ReorderPhotoCollageItemsCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        block_gateway: LessonBlockGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._block_gateway: Final = block_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: ReorderPhotoCollageItemsCommand) -> None:
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

        block.reorder_items(list(data.ordered_ids))
        await self._block_gateway.reorder_photo_collage_items(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
