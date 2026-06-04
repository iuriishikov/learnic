from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    LessonRenamedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RenameNoteLessonCommand:
    actor_id: UserID
    lesson_id: NoteLessonID
    title: str


@final
class RenameNoteLessonCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        lesson_gateway: NoteLessonGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: RenameNoteLessonCommand) -> None:
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
        lesson.rename(LessonTitle(data.title))
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=LessonRenamedPayload(
                lesson_id=str(lesson.oid),
                title=lesson.title.value,
            ),
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
