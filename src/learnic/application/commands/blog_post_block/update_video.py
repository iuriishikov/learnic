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
from learnic.entities.blog_post_block.models import BlogVideoBlock
from learnic.entities.blog_post_block.value_objects import BlogBlockCaption
from learnic.entities.user.models import UserID

_VIDEO_CONTENT_TYPE_PREFIX: Final[str] = "video/"


@dataclass(slots=True, frozen=True)
class UpdateBlogVideoBlockCommand:
    actor_id: UserID
    block_id: BlogPostBlockID
    upload: IncomingUpload | None
    title: str | None


@final
class UpdateBlogVideoBlockCommandHandler:
    """Replace a video block's file and/or title.

    Same full-replace PATCH semantics as the image counterpart, with
    a ``video/`` content-type contract.
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

    async def run(self, data: UpdateBlogVideoBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, BlogVideoBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlogPostBlockType.VIDEO.value,
                actual=block.type.value,
            )

        previous_file_id = None
        if data.upload is not None:
            if not data.upload.content_type.startswith(
                _VIDEO_CONTENT_TYPE_PREFIX,
            ):
                raise WrongFileContentTypeError(
                    file_id="<upload>",
                    expected_prefix=_VIDEO_CONTENT_TYPE_PREFIX,
                    actual=data.upload.content_type,
                )
            previous_file_id = block.file_id
            new_file = await self._file_uploads.upload_stream(
                data.upload,
                data.actor_id,
            )
            block.update_file(new_file.oid)

        block.update_title(
            BlogBlockCaption(data.title)
            if data.title is not None
            else None,
        )
        await self._block_gateway.update_video(block)
        if previous_file_id is not None:
            await self._file_uploads.soft_delete_previous(previous_file_id)
        await self._transaction.commit()
