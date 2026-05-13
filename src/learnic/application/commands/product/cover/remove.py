from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    CoverRemovedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RemoveProductCoverCommand:
    actor_id: UserID
    product_id: ProductID


@final
class RemoveProductCoverCommandHandler:
    """Detaches cover from product and soft-deletes the file row."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        files_gateway: FilesGateway,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._files_gateway: Final = files_gateway
        self._event_bus: Final = event_bus

    async def run(self, data: RemoveProductCoverCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_COVER,
        )

        previous_file_id = product.remove_cover()
        if previous_file_id is not None:
            previous_file = await self._files_gateway.with_id(previous_file_id)
            if previous_file is not None and not previous_file.is_deleted:
                previous_file.mark_deleted()
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=CoverRemovedPayload(),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
