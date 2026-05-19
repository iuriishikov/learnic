from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    PriceChangedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import ProductPriceAmount
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductPriceCommand:
    actor_id: UserID
    product_id: ProductID
    amount: int


@final
class ChangeProductPriceCommandHandler:
    """Set or update the price of a product the actor owns.

    Owner-only — non-author collaborators cannot change pricing,
    regardless of any roles they hold on the product. ``amount``
    is in minor units of currency (kopecks for RUB) and is bounded
    by ``[PRICE_AMOUNT_MIN, PRICE_AMOUNT_MAX]``; a zero amount is
    permitted to mark the product as free-but-sellable.
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

    async def run(self, data: ChangeProductPriceCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        new_price = ProductPriceAmount(data.amount)
        product.set_price(new_price)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=PriceChangedPayload(amount=new_price.value),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
