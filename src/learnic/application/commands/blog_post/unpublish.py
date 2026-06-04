from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.blog_post.ids import BlogPostID


@dataclass(slots=True, frozen=True)
class UnpublishBlogPostCommand:
    post_id: BlogPostID


@final
class UnpublishBlogPostCommandHandler:
    """Unpublish a blog post (PUBLISHED -> DRAFT), hiding it again."""

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway

    async def run(self, data: UnpublishBlogPostCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)
        post.unpublish()
        await self._transaction.commit()
