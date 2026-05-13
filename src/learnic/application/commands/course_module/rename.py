from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ModuleRenamedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.course_module import (
    CourseModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.value_objects import ModuleTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RenameCourseModuleCommand:
    actor_id: UserID
    module_id: CourseModuleID
    title: str


@final
class RenameCourseModuleCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        module_gateway: CourseModuleGateway,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: RenameCourseModuleCommand) -> None:
        module = await self._module_gateway.with_id(data.module_id)
        if module is None:
            raise EntityNotFoundError(data.module_id)
        product = await self._product_gateway.with_id(module.product_id)
        if product is None:
            raise EntityNotFoundError(module.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(module.product_id),
            Permission.EDIT_MODULES,
        )
        module.rename(ModuleTitle(data.title))
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=ModuleRenamedPayload(
                module_id=str(module.oid),
                title=module.title.value,
            ),
            product_id=module.product_id,
            actor_id=data.actor_id,
        )
