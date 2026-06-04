from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import BlogHtmlBlock
from learnic.entities.blog_post_block.value_objects import BlogHtmlContent
from learnic.entities.common.limits import BLOG_POST_BLOCK_LIMIT


@dataclass(slots=True, frozen=True)
class AddBlogHtmlBlockCommand:
    post_id: BlogPostID
    html: str  # raw HTML — will be sanitized server-side


@final
class AddBlogHtmlBlockCommandHandler:
    """Append a new HTML block to a blog post."""

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
        block_gateway: BlogPostBlockGateway,
        html_sanitizer: HtmlSanitizer,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway
        self._block_gateway: Final = block_gateway
        self._html_sanitizer: Final = html_sanitizer

    async def run(self, data: AddBlogHtmlBlockCommand) -> BlogPostBlockID:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        await self._block_gateway.lock_for_post(data.post_id)
        existing = await self._block_gateway.list_for_post(data.post_id)
        BLOG_POST_BLOCK_LIMIT.ensure(len(existing))
        next_position = max((b.position for b in existing), default=-1) + 1

        sanitized = self._html_sanitizer.sanitize(data.html)
        block = BlogHtmlBlock.create(
            post_id=data.post_id,
            html=BlogHtmlContent(sanitized),
            position=next_position,
        )
        await self._block_gateway.add_html(block)
        await self._transaction.commit()
        return block.oid
