from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import ProductDescription
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ChangeProductDescriptionCommand:
    actor_id: UserID
    product_id: ProductID
    html: str


@final
class ChangeProductDescriptionCommandHandler:
    """Sanitizes user-supplied HTML, then updates the product description."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        html_sanitizer: HtmlSanitizer,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._html_sanitizer: Final = html_sanitizer
        self._event_bus: Final = event_bus

    async def run(self, data: ChangeProductDescriptionCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_DESCRIPTION,
        )
        sanitized = self._html_sanitizer.sanitize(data.html)
        new_description = ProductDescription(sanitized)
        product.change_description(new_description)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.DESCRIPTION_CHANGED,
            product_id=product.oid,
            actor_id=data.actor_id,
            payload={"description": new_description.value},
        )
