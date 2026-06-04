from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.value_objects import BlogPostTitle


@dataclass(slots=True, frozen=True)
class RenameBlogPostCommand:
    post_id: BlogPostID
    title: str


@final
class RenameBlogPostCommandHandler:
    """Change a blog post's title."""

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway

    async def run(self, data: RenameBlogPostCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)
        post.rename(BlogPostTitle(data.title))
        await self._transaction.commit()
