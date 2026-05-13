from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    CannotPublishCourseDirectlyError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    PublishedPayload,
    publish_product_event,
)
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class PublishProductCommand:
    actor_id: UserID
    product_id: ProductID


@final
class PublishProductCommandHandler:
    """Marks a webinar product published.

    Course products cannot be published via this endpoint —
    they are published implicitly by creating their first
    release. Direct publish attempts on courses raise
    :class:`CannotPublishCourseDirectlyError`.
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

    async def run(self, data: PublishProductCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.PUBLISH,
        )
        if product.type is ProductType.COURSE:
            raise CannotPublishCourseDirectlyError(data.product_id)
        was_published = product.status is ProductStatus.PUBLISHED
        product.publish()
        await self._transaction.commit()
        if was_published:
            return
        assert product.published_at is not None
        await publish_product_event(
            self._event_bus,
            payload=PublishedPayload(
                status=product.status.value,
                published_at=product.published_at.isoformat(),
            ),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
