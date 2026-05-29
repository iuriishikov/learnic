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
from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.application.common.persistence.course_module import (
    CourseModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddCourseLessonCommand:
    actor_id: UserID
    module_id: CourseModuleID
    title: str


@final
class AddCourseLessonCommandHandler:
    """Append a new lesson to a module's draft."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        module_gateway: CourseModuleGateway,
        lesson_gateway: CourseLessonGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._lesson_gateway: Final = lesson_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: AddCourseLessonCommand) -> CourseLessonID:
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
        next_position = max((lsn.position for lsn in existing), default=-1) + 1

        lesson = CourseLesson.create(
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
