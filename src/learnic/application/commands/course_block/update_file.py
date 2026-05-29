from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import FileBlock
from learnic.entities.course_block.value_objects import BlockTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateFileBlockCommand:
    """Mutate the file block; one of two paths.

    * ``data`` + ``content_type`` present → upload a new file and
      attach it; the previously-attached file is soft-deleted via
      :class:`FileUploadService.soft_delete_previous`.
    * Both absent → only ``title`` is touched (set / clear).

    The two paths share one command shape so the route can stay a
    single ``PATCH /...`` accepting an optional ``UploadFile``.
    """

    actor_id: UserID
    block_id: LessonBlockID
    data: bytes | None
    content_type: str | None
    title: str | None


@final
class UpdateFileBlockCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        block_gateway: LessonBlockGateway,
        file_uploads: FileUploadService,
        entitlement: EntitlementService,
        event_bus: ContentEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus

    async def run(self, data: UpdateFileBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, FileBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlockType.FILE.value,
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

        if data.data is not None and data.content_type is not None:
            previous_file_id = block.file_id
            freed_bytes = await self._file_uploads.previous_file_size(
                previous_file_id,
            )
            await self._entitlement.ensure_can_replace_upload(
                product.author_id,
                added_bytes=len(data.data),
                freed_bytes=freed_bytes,
            )
            new_file = await self._file_uploads.upload(
                data.data,
                data.content_type,
                data.actor_id,
            )
            block.update_file(new_file.oid)
            await self._file_uploads.soft_delete_previous(previous_file_id)

        block.update_title(
            BlockTitle(data.title) if data.title is not None else None,
        )
        await self._block_gateway.update_file(block)
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=BlockUpdatedPayload.from_entity(block),
            product_id=block.product_id,
            actor_id=data.actor_id,
        )
