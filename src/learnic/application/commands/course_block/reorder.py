from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlocksReorderedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidReorderError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ReorderLessonBlocksCommand:
    actor_id: UserID
    lesson_id: CourseLessonID
    ordered_ids: list[LessonBlockID]


@final
class ReorderLessonBlocksCommandHandler:
    """Replace block ordering inside a lesson atomically.

    ``ordered_ids`` must equal the existing block set of the
    lesson exactly (irrespective of block types — all 4 types share
    one position-space within a lesson).
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: CourseLessonGateway,
        block_gateway: LessonBlockGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._block_gateway: Final = block_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: ReorderLessonBlocksCommand) -> None:
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
        existing_ids = {b.oid for b in existing}
        provided_ids = set(data.ordered_ids)
        if len(data.ordered_ids) != len(provided_ids) or provided_ids != existing_ids:
            raise InvalidReorderError

        await self._block_gateway.reorder(data.lesson_id, data.ordered_ids)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlocksReorderedPayload(
                lesson_id=str(data.lesson_id),
                ordered_ids=[str(oid) for oid in data.ordered_ids],
            ),
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
