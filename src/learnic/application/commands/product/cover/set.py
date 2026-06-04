from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    CoverChangedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SetProductCoverCommand:
    actor_id: UserID
    product_id: ProductID
    upload: IncomingUpload


@final
class SetProductCoverCommandHandler:
    """Uploads a new cover image, attaches it, soft-deletes the old one."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        file_uploads: FileUploadService,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus

    async def run(self, data: SetProductCoverCommand) -> FileID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_COVER,
        )

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.actor_id,
        )
        previous_file_id = product.set_cover(file.oid)
        await self._file_uploads.soft_delete_previous(previous_file_id)

        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=CoverChangedPayload(cover_file_id=str(file.oid)),
            product_id=product.oid,
            actor_id=data.actor_id,
        )
        return file.oid
