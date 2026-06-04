from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.models import (
    BlogImageBlock,
    BlogVideoBlock,
)
from learnic.entities.file.ids import FileID


@dataclass(slots=True, frozen=True)
class DeleteBlogPostCommand:
    post_id: BlogPostID


@final
class DeleteBlogPostCommandHandler:
    """Hard-delete a blog post and reclaim its media.

    Child block rows cascade via FK; the file rows behind image/video
    blocks do not (the FK runs file -> block, not the reverse), so the
    post's media would orphan in storage. We collect those file ids
    before deletion and soft-delete + S3-purge each one — mirroring
    the author-facing note delete so the operation actually frees
    storage instead of leaking blobs.
    """

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
        block_gateway: BlogPostBlockGateway,
        file_uploads: FileUploadService,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway
        self._block_gateway: Final = block_gateway
        self._file_uploads: Final = file_uploads

    async def run(self, data: DeleteBlogPostCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        blocks = await self._block_gateway.list_for_post(post.oid)
        file_ids: list[FileID] = [
            block.file_id
            for block in blocks
            if isinstance(block, (BlogImageBlock, BlogVideoBlock))
        ]

        await self._blog_post_gateway.delete(post)
        for file_id in file_ids:
            await self._file_uploads.soft_delete_previous(file_id)
        await self._transaction.commit()
