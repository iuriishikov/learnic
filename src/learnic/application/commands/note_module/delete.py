from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ModuleDeletedPayload,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.file import FilesReader
from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteNoteModuleCommand:
    actor_id: UserID
    module_id: NoteModuleID


@final
class DeleteNoteModuleCommandHandler:
    """Hard-delete a module. Cascades to lessons and their blocks.

    The cascade silently drops file / video-file / collage block
    rows across every lesson of the module, so their files are
    snapshotted BEFORE the delete and soft-deleted alongside it —
    otherwise the rows would linger live (quota-invisible) and the
    S3 blobs would orphan forever. Same sweep discipline as
    block-level, lesson-level, and product-level deletes.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        module_gateway: NoteModuleGateway,
        files_reader: FilesReader,
        file_uploads: FileUploadService,
        event_bus: ContentEventBus,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._module_gateway: Final = module_gateway
        self._files_reader: Final = files_reader
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus
        self._quota_publisher: Final = quota_publisher

    async def run(self, data: DeleteNoteModuleCommand) -> None:
        module = await self._module_gateway.with_id(data.module_id)
        if module is None:
            raise EntityNotFoundError(data.module_id)
        product = await self._product_gateway.with_id(module.product_id)
        if product is None:
            raise EntityNotFoundError(module.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(module.product_id),
            Permission.EDIT_MODULES,
        )
        product_id = module.product_id
        # Snapshot the module's file references BEFORE the cascade —
        # afterwards the lesson + block rows are gone and the
        # union-walk would return nothing.
        file_ids = await self._files_reader.file_ids_for_module(
            data.module_id,
        )
        await self._module_gateway.delete(module)
        for file_id in file_ids:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=ModuleDeletedPayload(module_id=str(data.module_id)),
            product_id=product_id,
            actor_id=data.actor_id,
        )
        if file_ids:
            await self._quota_publisher.usage_changed(product.author_id)
