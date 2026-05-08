from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import S3Config


@dataclass(slots=True, frozen=True)
class SetProductCoverCommand:
    actor_id: UserID
    product_id: ProductID
    data: bytes
    content_type: str


@final
class SetProductCoverCommandHandler:
    """Uploads a new cover image, attaches it, soft-deletes the old one."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        files_gateway: FilesGateway,
        file_storage: FileStorage,
        s3_config: S3Config,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._files_gateway: Final = files_gateway
        self._file_storage: Final = file_storage
        self._s3_config: Final = s3_config
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

        content_type = ContentType(data.content_type)
        size_bytes = FileSize(len(data.data))
        bucket = StorageBucket(self._s3_config.bucket)

        file = File.create_file(
            bucket=bucket,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=data.actor_id,
        )

        await self._file_storage.put(
            bucket=bucket.value,
            name=file.storage_name.value,
            data=data.data,
            content_type=data.content_type,
        )
        self._entity_saver.add_one(file)
        await self._transaction.flush()

        previous_file_id = product.set_cover(file.oid)
        if previous_file_id is not None:
            previous_file = await self._files_gateway.with_id(previous_file_id)
            if previous_file is not None and not previous_file.is_deleted:
                previous_file.mark_deleted()

        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.COVER_CHANGED,
            product_id=product.oid,
            actor_id=data.actor_id,
            payload={"cover_file_id": str(file.oid)},
        )
        return file.oid
