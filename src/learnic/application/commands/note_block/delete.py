from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockDeletedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import (
    FileBlock,
    PhotoCollageBlock,
    VideoFileBlock,
)
from learnic.entities.file.ids import FileID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteLessonBlockCommand:
    actor_id: UserID
    block_id: LessonBlockID


@final
class DeleteLessonBlockCommandHandler:
    """Hard-delete a block. Child rows cascade via FK."""

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus

    async def run(self, data: DeleteLessonBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        product = await self._product_gateway.with_id(block.product_id)
        if product is None:
            raise EntityNotFoundError(block.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(block.product_id),
            Permission.EDIT_LESSONS,
        )
        product_id = block.product_id
        file_ids = _file_ids_of(block)
        await self._block_gateway.delete(block.oid)
        # File-backed blocks (file / video-file / collage) lose their
        # last reference when the row goes; soft-delete + S3 purge
        # those file rows so the deletion actually frees storage
        # instead of orphaning blobs.
        for file_id in file_ids:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockDeletedPayload(block_id=str(data.block_id)),
            product_id=product_id,
            actor_id=data.actor_id,
        )


def _file_ids_of(
    block: FileBlock | VideoFileBlock | PhotoCollageBlock | object,
) -> list[FileID]:
    """Return every file the block exclusively held a reference to.

    File / video-file blocks carry a single nullable ``file_id``;
    collage blocks carry a list of items, each with a (nullable)
    ``file_id``. Non-file block types (HTML, KaTeX, choice, ...)
    return an empty list.
    """
    if isinstance(block, (FileBlock, VideoFileBlock)):
        return [block.file_id] if block.file_id is not None else []
    if isinstance(block, PhotoCollageBlock):
        return [
            item.file_id
            for item in block.items
            if item.file_id is not None
        ]
    return []
