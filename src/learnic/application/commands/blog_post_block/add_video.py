from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongFileContentTypeError,
)
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import BlogVideoBlock
from learnic.entities.blog_post_block.value_objects import BlogBlockCaption
from learnic.entities.common.limits import BLOG_POST_BLOCK_LIMIT
from learnic.entities.user.models import UserID

_VIDEO_CONTENT_TYPE_PREFIX: Final[str] = "video/"


@dataclass(slots=True, frozen=True)
class AddBlogVideoBlockCommand:
    actor_id: UserID
    post_id: BlogPostID
    upload: IncomingUpload
    title: str | None = None


@final
class AddBlogVideoBlockCommandHandler:
    """Upload a video and append a video block to a blog post.

    Sibling of :class:`AddBlogImageBlockCommandHandler` with a
    ``video/`` content-type contract; the prefix check fires before
    the upload so a mislabelled file never reaches storage.
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

    async def run(self, data: AddBlogVideoBlockCommand) -> BlogPostBlockID:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        if not data.upload.content_type.startswith(
            _VIDEO_CONTENT_TYPE_PREFIX,
        ):
            raise WrongFileContentTypeError(
                file_id="<upload>",
                expected_prefix=_VIDEO_CONTENT_TYPE_PREFIX,
                actual=data.upload.content_type,
            )

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.actor_id,
        )

        title = (
            BlogBlockCaption(data.title)
            if data.title is not None
            else None
        )
        await self._block_gateway.lock_for_post(data.post_id)
        existing = await self._block_gateway.list_for_post(data.post_id)
        BLOG_POST_BLOCK_LIMIT.ensure(len(existing))
        next_position = max((b.position for b in existing), default=-1) + 1

        block = BlogVideoBlock.create(
            post_id=data.post_id,
            file_id=file.oid,
            position=next_position,
            title=title,
        )
        await self._block_gateway.add_video(block)
        await self._transaction.commit()
        return block.oid
