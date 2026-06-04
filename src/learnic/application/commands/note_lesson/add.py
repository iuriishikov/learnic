from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    LessonAddedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.common.limits import NOTE_LESSON_LIMIT
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddNoteLessonCommand:
    actor_id: UserID
    module_id: NoteModuleID
    title: str


@final
class AddNoteLessonCommandHandler:
    """Append a new lesson to a module's draft."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        module_gateway: NoteModuleGateway,
        lesson_gateway: NoteLessonGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddNoteLessonCommand) -> NoteLessonID:
        module = await self._module_gateway.with_id(data.module_id)
        if module is None:
            raise EntityNotFoundError(data.module_id)
        product = await self._product_gateway.with_id(module.product_id)
        if product is None:
            raise EntityNotFoundError(module.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(module.product_id),
            Permission.EDIT_LESSONS,
        )

        await self._lesson_gateway.lock_for_module(data.module_id)
        existing = await self._lesson_gateway.for_module(data.module_id)
        NOTE_LESSON_LIMIT.ensure(len(existing))
        next_position = max((lsn.position for lsn in existing), default=-1) + 1

        lesson = NoteLesson.create(
            module_id=data.module_id,
            product_id=module.product_id,
            title=LessonTitle(data.title),
            position=next_position,
        )
        self._entity_saver.add_one(lesson)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=LessonAddedPayload.from_entity(
                module_id=data.module_id,
                lesson=lesson,
            ),
            product_id=module.product_id,
            actor_id=data.actor_id,
        )
        return lesson.oid
