from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import BlogImageBlock
from learnic.entities.blog_post_block.value_objects import BlogBlockCaption
from learnic.entities.user.models import UserID

_IMAGE_CONTENT_TYPE_PREFIX: Final[str] = "image/"


@dataclass(slots=True, frozen=True)
class UpdateBlogImageBlockCommand:
    actor_id: UserID
    block_id: BlogPostBlockID
    upload: IncomingUpload | None
    caption: str | None


@final
class UpdateBlogImageBlockCommandHandler:
    """Replace an image block's file and/or caption.

    A full-replace PATCH: ``upload=None`` keeps the current image,
    ``caption=None`` clears the caption. When a new file is supplied
    the ``image/`` prefix is re-checked and the previous file is
    soft-deleted + S3-purged so the swap frees storage.
    """

    def __init__(
        self,
        transaction: Transaction,
        block_gateway: BlogPostBlockGateway,
        file_uploads: FileUploadService,
    ) -> None:
        self._transaction: Final = transaction
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads

    async def run(self, data: UpdateBlogImageBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, BlogImageBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlogPostBlockType.IMAGE.value,
                actual=block.type.value,
            )

        previous_file_id = None
        if data.upload is not None:
            if not data.upload.content_type.startswith(
                _IMAGE_CONTENT_TYPE_PREFIX,
            ):
                raise WrongFileContentTypeError(
                    file_id="<upload>",
                    expected_prefix=_IMAGE_CONTENT_TYPE_PREFIX,
                    actual=data.upload.content_type,
                )
            previous_file_id = block.file_id
            new_file = await self._file_uploads.upload_stream(
                data.upload,
                data.actor_id,
            )
            block.update_file(new_file.oid)

        block.update_caption(
            BlogBlockCaption(data.caption)
            if data.caption is not None
            else None,
        )
        await self._block_gateway.update_image(block)
        if previous_file_id is not None:
            await self._file_uploads.soft_delete_previous(previous_file_id)
        await self._transaction.commit()
