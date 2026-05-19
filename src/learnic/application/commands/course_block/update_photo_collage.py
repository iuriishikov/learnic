from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.commands.course_block.add_photo_collage import (
    CollageItemUpload,
)
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.file import FilesReader
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import CollageItem, PhotoCollageBlock
from learnic.entities.course_block.value_objects import (
    BlockTitle,
    CollageCaption,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID

_IMAGE_CONTENT_TYPE_PREFIX: Final[str] = "image/"


@dataclass(slots=True, frozen=True)
class UpdatePhotoCollageBlockCommand:
    """Atomic full-replace of a collage's items + title.

    The new ``items`` tuple is the complete new state — there is no
    per-item diff, no "keep these existing files" knob. The author
    re-uploads everything they want in the new state. Older item
    files are NOT soft-deleted by this command (they may still be
    referenced from other blocks); the file-lifecycle worker reaps
    truly-unreferenced files on its own cadence.
    """

    actor_id: UserID
    block_id: LessonBlockID
    items: tuple[CollageItemUpload, ...]
    title: str | None


@final
class UpdatePhotoCollageBlockCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        files_reader: FilesReader,
        entitlement: EntitlementService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._files_reader: Final = files_reader
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus

    async def _validate_and_upload(
        self,
        items: tuple[CollageItemUpload, ...],
        actor_id: UserID,
    ) -> list[CollageItem]:
        # Content-type and quota are checked in run() before we get
        # here — this method only does the S3 writes + entity build.
        out: list[CollageItem] = []
        for src in items:
            file = await self._file_uploads.upload(
                src.data,
                src.content_type,
                actor_id,
            )
            caption = (
                CollageCaption(src.caption) if src.caption is not None else None
            )
            out.append(CollageItem(file_id=file.oid, caption=caption))
        return out

    async def run(self, data: UpdatePhotoCollageBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, PhotoCollageBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.PHOTO_COLLAGE.value,
                actual=block.type.value,
            )
        product = await self._product_gateway.with_id(block.product_id)
        if product is None:
            raise EntityNotFoundError(block.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(block.product_id),
            Permission.EDIT_LESSONS,
        )

        for src in data.items:
            if not src.content_type.startswith(_IMAGE_CONTENT_TYPE_PREFIX):
                raise WrongFileContentTypeError(
                    file_id="<upload>",
                    expected_prefix=_IMAGE_CONTENT_TYPE_PREFIX,
                    actual=src.content_type,
                )

        added_bytes = sum(len(src.data) for src in data.items)
        old_file_ids = [
            item.file_id for item in block.items if item.file_id is not None
        ]
        old_file_metas = await self._files_reader.with_ids(old_file_ids)
        freed_bytes = sum(meta.size_bytes for meta in old_file_metas.values())
        await self._entitlement.ensure_can_replace_upload(
            product.author_id,
            added_bytes=added_bytes,
            freed_bytes=freed_bytes,
        )

        items = await self._validate_and_upload(data.items, data.actor_id)
        block.replace_items(items)
        block.update_title(
            BlockTitle(data.title) if data.title is not None else None,
        )
        await self._block_gateway.update_photo_collage(block)
        # Old item files lose their last reference here — soft-delete
        # the rows and enqueue S3 purge so the replacement doesn't
        # orphan blobs (the FileUsageReader already stops counting
        # them, but without this loop they'd cost storage forever).
        for old_file_id in old_file_ids:
            await self._file_uploads.soft_delete_previous(old_file_id)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
