from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    ProductNameAlreadyTakenError,
)
from learnic.application.common.persistence.product import (
    ProductGateway,
    ProductReader,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductNameCommand:
    actor_id: UserID
    product_id: ProductID
    value: str


@final
class ChangeProductNameCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        product_reader: ProductReader,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._product_reader: Final = product_reader
        self._event_bus: Final = event_bus

    async def run(self, data: ChangeProductNameCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_DESCRIPTION,
        )
        new_name = ProductTitle(data.value)
        if (
            new_name.value != product.name.value
            and await self._product_reader.name_exists(
                product.author_id,
                new_name.value,
                exclude_oid=product.oid,
            )
        ):
            raise ProductNameAlreadyTakenError(new_name.value)
        product.rename(new_name)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.NAME_CHANGED,
            product_id=product.oid,
            actor_id=data.actor_id,
            payload={"name": new_name.value},
        )
