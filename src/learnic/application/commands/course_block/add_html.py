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
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import HtmlBlock
from learnic.entities.course_block.value_objects import HtmlContent
from learnic.entities.common.limits import LESSON_BLOCK_LIMIT
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddHtmlBlockCommand:
    actor_id: UserID
    lesson_id: CourseLessonID
    html: str  # raw HTML — will be sanitized server-side


@final
class AddHtmlBlockCommandHandler:
    """Append a new HTML block to a lesson."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: CourseLessonGateway,
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

        await self._block_gateway.lock_for_lesson(data.lesson_id)
        existing = await self._block_gateway.list_for_lesson(data.lesson_id)
        LESSON_BLOCK_LIMIT.ensure(len(existing))
        next_position = max((b.position for b in existing), default=-1) + 1

        sanitized = self._html_sanitizer.sanitize(data.html)
        block = HtmlBlock.create(
            lesson_id=data.lesson_id,
            product_id=lesson.product_id,
            html=HtmlContent(sanitized),
            position=next_position,
        )
        await self._block_gateway.add_html(block)
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
