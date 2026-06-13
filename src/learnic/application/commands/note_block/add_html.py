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
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import HtmlBlock
from learnic.entities.note_block.value_objects import HtmlContent
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddHtmlBlockCommand:
    actor_id: UserID
    lesson_id: NoteLessonID
    html: str  # raw HTML — will be sanitized server-side


@final
class AddHtmlBlockCommandHandler:
    """Append a new HTML block to a lesson."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        block_gateway: LessonBlockGateway,
        html_sanitizer: HtmlSanitizer,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._html_sanitizer: Final = html_sanitizer
        self._event_bus: Final = event_bus

    async def run(self, data: AddHtmlBlockCommand) -> LessonBlockID:
        lesson, next_position = await prepare_block_append(
            actor_id=data.actor_id,
            lesson_id=data.lesson_id,
            authorizer=self._authorizer,
            product_gateway=self._product_gateway,
            lesson_gateway=self._lesson_gateway,
            block_gateway=self._block_gateway,
        )

        sanitized = await self._html_sanitizer.sanitize(data.html)
        block = HtmlBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            html=HtmlContent(sanitized),
            position=next_position,
        )
        await self._block_gateway.add_html(block)
        await commit_and_publish_added(
            transaction=self._transaction,
            event_bus=self._event_bus,
            lesson_id=data.lesson_id,
            block=block,
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
        return block.oid
