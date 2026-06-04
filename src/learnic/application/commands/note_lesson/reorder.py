from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    LessonsReorderedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidReorderError,
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
class ReorderNoteLessonsCommand:
    actor_id: UserID
    module_id: NoteModuleID
    ordered_ids: list[NoteLessonID]


@final
class ReorderNoteLessonsCommandHandler:
    """Replace lesson ordering inside a module atomically."""

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

    async def run(self, data: ReorderNoteLessonsCommand) -> None:
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
        existing_ids = {lsn.oid for lsn in existing}
        provided_ids = set(data.ordered_ids)
        if len(data.ordered_ids) != len(provided_ids) or provided_ids != existing_ids:
            raise InvalidReorderError

        await self._lesson_gateway.reorder(
            data.module_id,
            data.ordered_ids,
        )
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=LessonsReorderedPayload(
                module_id=str(data.module_id),
                ordered_ids=[str(oid) for oid in data.ordered_ids],
            ),
            product_id=module.product_id,
            actor_id=data.actor_id,
        )
