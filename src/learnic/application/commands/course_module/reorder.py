from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ContentEventKind,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidReorderError,
)
from learnic.application.common.persistence.course_module import (
    CourseModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ReorderCourseModulesCommand:
    actor_id: UserID
    product_id: ProductID
    ordered_ids: list[CourseModuleID]


@final
class ReorderCourseModulesCommandHandler:
    """Replace module ordering atomically with the supplied sequence.

    ``ordered_ids`` must be exactly the set of existing modules of
    the product — no missing, no extra, no duplicates. Otherwise
    :class:`InvalidReorderError` is raised.
    """

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

    async def run(self, data: ReorderCourseModulesCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_MODULES,
        )

        existing = await self._module_gateway.for_product(data.product_id)
        existing_ids = {m.oid for m in existing}
        provided_ids = set(data.ordered_ids)
        if len(data.ordered_ids) != len(provided_ids) or provided_ids != existing_ids:
            raise InvalidReorderError

        await self._module_gateway.reorder(
            data.product_id,
            data.ordered_ids,
        )
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            kind=ContentEventKind.MODULES_REORDERED,
            product_id=data.product_id,
            actor_id=data.actor_id,
            payload={"ordered_ids": [str(oid) for oid in data.ordered_ids]},
        )
