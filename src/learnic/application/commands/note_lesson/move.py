from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    LessonMovedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    CrossNoteLessonMoveError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class MoveNoteLessonCommand:
    actor_id: UserID
    lesson_id: NoteLessonID
    target_module_id: NoteModuleID


@final
class MoveNoteLessonCommandHandler:
    """Move a lesson to a different module within the same note.

    Cross-note moves are forbidden — they would invalidate the
    ``product_id`` denorm on lessons. The lesson is appended to the
    end of the target module (use full-reorder afterwards to place
    it precisely).
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        module_gateway: NoteModuleGateway,
        lesson_gateway: NoteLessonGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: MoveNoteLessonCommand) -> None:
        lesson = await self._lesson_gateway.with_id(data.lesson_id)
        if lesson is None:
            raise EntityNotFoundError(data.lesson_id)
        target_module = await self._module_gateway.with_id(
            data.target_module_id,
        )
        if target_module is None:
            raise EntityNotFoundError(data.target_module_id)
        product = await self._product_gateway.with_id(lesson.product_id)
        if product is None:
            raise EntityNotFoundError(lesson.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(lesson.product_id),
            Permission.EDIT_LESSONS,
        )
        if target_module.product_id != lesson.product_id:
            raise CrossNoteLessonMoveError(
                lesson_id=data.lesson_id,
                source_product_id=lesson.product_id,
                target_product_id=target_module.product_id,
            )
        if target_module.oid == lesson.module_id:
            return  # no-op

        await self._lesson_gateway.lock_for_module(target_module.oid)
        target_lessons = await self._lesson_gateway.for_module(
            target_module.oid,
        )
        next_position = max((lsn.position for lsn in target_lessons), default=-1) + 1
        from_module_id = lesson.module_id  # captured before the mutation
        lesson.move_to_module(target_module.oid, next_position)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=LessonMovedPayload.of(
                lesson_id=lesson.oid,
                from_module_id=from_module_id,
                to_module_id=target_module.oid,
                position=lesson.position,
            ),
            product_id=lesson.product_id,
            actor_id=data.actor_id,
        )
