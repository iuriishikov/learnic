from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.note_block._append import (
    commit_and_publish_added,
    prepare_block_append,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.collaboration import (
    ContentEventBus,
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
from learnic.entities.note_lesson.ids import NoteLessonID
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
        lesson, next_position = await prepare_block_append(
            actor_id=data.actor_id,
            lesson_id=data.lesson_id,
            authorizer=self._authorizer,
            product_gateway=self._product_gateway,
            lesson_gateway=self._lesson_gateway,
            block_gateway=self._block_gateway,
        )

        external_id = RutubeVideoID.from_url(data.rutube_url)
        title = VideoTitle(data.title) if data.title is not None else None

        block = RutubeVideoBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            external_id=external_id,
            position=next_position,
            title=title,
        )
        await self._block_gateway.add_rutube_video(block)
        await commit_and_publish_added(
            transaction=self._transaction,
            event_bus=self._event_bus,
            lesson_id=data.lesson_id,
            block=block,
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
        return block.oid
