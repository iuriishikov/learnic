from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    VisibilityChangedPayload,
    publish_product_event,
)
from learnic.entities.product.enums import ProductVisibility
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductVisibilityCommand:
    actor_id: UserID
    product_id: ProductID
    visibility: ProductVisibility


@final
class ChangeProductVisibilityCommandHandler:
    """Switch a product between public and private visibility.

    Owner-only by design: the gate is
    :meth:`Authorizer.require_owner`, not a permission check, so the
    capability can never be delegated to a collaborator through a
    role. A no-op change (visibility already at the requested value)
    commits nothing extra and skips the event so subscribers don't
    see redundant deltas.
    """

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

    async def run(self, data: ChangeProductVisibilityCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require_owner(data.actor_id, data.product_id)
        if product.visibility is data.visibility:
            return
        product.change_visibility(data.visibility)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=VisibilityChangedPayload(
                visibility=product.visibility.value,
            ),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
