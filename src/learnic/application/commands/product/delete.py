from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
    ProductNotInDraftError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteProductCommand:
    actor_id: UserID
    product_id: ProductID


@final
class DeleteProductCommandHandler:
    """Hard-deletes a product, allowed only while it is still in draft.

    Once a product has been published (or later archived/banned),
    it likely has cohorts/enrollments hanging off it and removing
    it would erase commercial history. Authors must archive
    instead — admin tooling will be added later for permanent
    removal of archived products.
    """

    def __init__(
        self,
        transaction: Transaction,
        product_gateway: ProductGateway,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._product_gateway: Final = product_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: DeleteProductCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        if product.status is not ProductStatus.DRAFT:
            raise ProductNotInDraftError(
                data.product_id,
                product.status.value,
            )
        product_id = product.oid
        await self._product_gateway.delete(product)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.DELETED,
            product_id=product_id,
            actor_id=data.actor_id,
            payload={},
        )
