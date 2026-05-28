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
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import PhotoCollageBlock
from learnic.entities.course_block.value_objects import BlockTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdatePhotoCollageTitleCommand:
    """Set or clear a photo-collage block's title."""

    actor_id: UserID
    block_id: LessonBlockID
    title: str | None


@final
class UpdatePhotoCollageTitleCommandHandler:
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

    async def run(self, data: UpdatePhotoCollageTitleCommand) -> None:
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

        block.update_title(
            BlockTitle(data.title) if data.title is not None else None,
        )
        await self._block_gateway.update_photo_collage_title(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
