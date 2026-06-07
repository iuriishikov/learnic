from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.value_objects import (
    BlogPostSubtitle,
    BlogPostTopic,
)


@dataclass(slots=True, frozen=True)
class EditBlogPostMetaCommand:
    post_id: BlogPostID
    subtitle: str | None
    topic: str | None


def _subtitle(value: str | None) -> BlogPostSubtitle | None:
    """Wrap a present subtitle in its VO; a blank string clears it."""
    if value is None or not value.strip():
        return None
    return BlogPostSubtitle(value)


def _topic(value: str | None) -> BlogPostTopic | None:
    """Wrap a present topic in its VO; a blank string clears it."""
    if value is None or not value.strip():
        return None
    return BlogPostTopic(value)


@final
class EditBlogPostMetaCommandHandler:
    """Replace a blog post's editorial metadata.

    Sets the optional ``subtitle`` (short description under the title)
    and ``topic`` (category label above the title). Both are set
    wholesale — a ``None`` or blank value clears the field. The author's
    name and avatar are not stored here; they come from the post's
    ``created_by`` administrator on the read side.
    """

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway

    async def run(self, data: EditBlogPostMetaCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)
        post.edit_meta(
            _subtitle(data.subtitle),
            _topic(data.topic),
        )
        await self._transaction.commit()
