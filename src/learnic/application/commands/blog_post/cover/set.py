from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SetBlogPostCoverCommand:
    actor_id: UserID
    post_id: BlogPostID
    upload: IncomingUpload


@final
class SetBlogPostCoverCommandHandler:
    """Uploads a new cover image, attaches it, soft-deletes the old one.

    Admin-gated at the route boundary (the blog admin router), so the
    handler — like the other blog write handlers — carries no
    per-resource authorization of its own.
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

    async def run(self, data: SetBlogPostCoverCommand) -> FileID:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.actor_id,
        )
        previous_file_id = post.set_cover(file.oid)
        await self._file_uploads.soft_delete_previous(previous_file_id)

        await self._transaction.commit()
        return file.oid
