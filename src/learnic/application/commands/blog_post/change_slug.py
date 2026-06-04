from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    BlogPostSlugAlreadyTakenError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.value_objects import BlogPostSlug


@dataclass(slots=True, frozen=True)
class ChangeBlogPostSlugCommand:
    post_id: BlogPostID
    slug: str


@final
class ChangeBlogPostSlugCommandHandler:
    """Change a blog post's URL slug.

    The uniqueness check is skipped when the slug is unchanged (a
    no-op edit must not collide with the post's own row).
    """

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway

    async def run(self, data: ChangeBlogPostSlugCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)
        new_slug = BlogPostSlug(data.slug)
        if new_slug.value != post.slug.value and (
            await self._blog_post_gateway.slug_exists(new_slug.value)
        ):
            raise BlogPostSlugAlreadyTakenError(new_slug.value)
        post.change_slug(new_slug)
        await self._transaction.commit()
