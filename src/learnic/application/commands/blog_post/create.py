from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import BlogPostSlugAlreadyTakenError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostTitle,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CreateBlogPostCommand:
    actor_id: UserID
    title: str
    slug: str


@final
class CreateBlogPostCommandHandler:
    """Create a new blog post in ``DRAFT`` status.

    Admin-only — the route validates the platform-admin flag and
    passes the acting admin as ``actor_id`` (recorded as the post's
    ``created_by``). Slug uniqueness is checked up front so the SPA
    gets a precise 409 instead of an opaque unique-index violation.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        blog_post_gateway: BlogPostGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._blog_post_gateway: Final = blog_post_gateway

    async def run(self, data: CreateBlogPostCommand) -> BlogPostID:
        title = BlogPostTitle(data.title)
        slug = BlogPostSlug(data.slug)
        if await self._blog_post_gateway.slug_exists(slug.value):
            raise BlogPostSlugAlreadyTakenError(slug.value)

        post = BlogPost.create(
            title=title,
            slug=slug,
            created_by=data.actor_id,
        )
        self._entity_saver.add_one(post)
        await self._transaction.commit()
        return post.oid
