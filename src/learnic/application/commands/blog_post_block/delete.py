from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import (
    BlogImageBlock,
    BlogVideoBlock,
)


@dataclass(slots=True, frozen=True)
class DeleteBlogPostBlockCommand:
    block_id: BlogPostBlockID


@final
class DeleteBlogPostBlockCommandHandler:
    """Hard-delete a block; reclaim its backing file if it had one.

    The child row cascades via FK. Image/video blocks hold the last
    reference to their file, so we soft-delete + S3-purge it after
    removing the block (HTML blocks have no file and skip this).
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

    async def run(self, data: DeleteBlogPostBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)

        file_id = (
            block.file_id
            if isinstance(block, (BlogImageBlock, BlogVideoBlock))
            else None
        )
        await self._block_gateway.delete(block.oid)
        if file_id is not None:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
