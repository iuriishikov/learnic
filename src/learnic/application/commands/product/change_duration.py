from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    DurationChangedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import DurationHours
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductDurationCommand:
    actor_id: UserID
    product_id: ProductID
    value: int


@final
class ChangeProductDurationCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: ChangeProductDurationCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_DESCRIPTION,
        )
        new_duration = DurationHours(data.value)
        product.change_total_duration(new_duration)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=DurationChangedPayload(
                total_duration_in_hours=new_duration.value,
            ),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
