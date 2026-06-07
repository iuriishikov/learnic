from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.blog_post.ids import BlogPostID


@dataclass(slots=True, frozen=True)
class RemoveBlogPostCoverCommand:
    post_id: BlogPostID


@final
class RemoveBlogPostCoverCommandHandler:
    """Detaches the cover from a post and soft-deletes the file row.

    Admin-gated at the route boundary, so — like the other blog write
    handlers — it carries no per-resource authorization of its own.
    """

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
        file_uploads: FileUploadService,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway
        self._file_uploads: Final = file_uploads

    async def run(self, data: RemoveBlogPostCoverCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        previous_file_id = post.remove_cover()
        await self._file_uploads.soft_delete_previous(previous_file_id)
        await self._transaction.commit()
