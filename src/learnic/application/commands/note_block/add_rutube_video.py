from dataclasses import dataclass
from typing import Final, final

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
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import RutubeVideoBlock
from learnic.entities.note_block.value_objects import (
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.common.limits import LESSON_BLOCK_LIMIT
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddRutubeVideoBlockCommand:
    actor_id: UserID
    lesson_id: NoteLessonID
    rutube_url: str
    title: str | None = None


@final
class AddRutubeVideoBlockCommandHandler:
    """Append a new Rutube-embed block to a lesson.

    The handler parses the URL into the canonical 32-hex
    Rutube video id; if a different provider is added later it
    will get its own command/handler/route rather than a shared
    ``provider`` discriminator.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        block_gateway: LessonBlockGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddRutubeVideoBlockCommand) -> LessonBlockID:
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

        external_id = RutubeVideoID.from_url(data.rutube_url)
        title = VideoTitle(data.title) if data.title is not None else None

        await self._block_gateway.lock_for_lesson(data.lesson_id)
        existing = await self._block_gateway.list_for_lesson(data.lesson_id)
        LESSON_BLOCK_LIMIT.ensure(len(existing))
        next_position = max((b.position for b in existing), default=-1) + 1

        block = RutubeVideoBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            external_id=external_id,
            position=next_position,
            title=title,
        )
        await self._block_gateway.add_rutube_video(block)
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
