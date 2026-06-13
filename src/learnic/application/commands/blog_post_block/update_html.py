from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import BlogHtmlBlock
from learnic.entities.blog_post_block.value_objects import BlogHtmlContent


@dataclass(slots=True, frozen=True)
class UpdateBlogHtmlBlockCommand:
    block_id: BlogPostBlockID
    html: str  # raw HTML — will be sanitized server-side


@final
class UpdateBlogHtmlBlockCommandHandler:
    """Replace the body of an existing HTML block."""

    def __init__(
        self,
        transaction: Transaction,
        block_gateway: BlogPostBlockGateway,
        html_sanitizer: HtmlSanitizer,
    ) -> None:
        self._transaction: Final = transaction
        self._block_gateway: Final = block_gateway
        self._html_sanitizer: Final = html_sanitizer

    async def run(self, data: UpdateBlogHtmlBlockCommand) -> None:
        block = await self._block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)
        if not isinstance(block, BlogHtmlBlock):
            raise WrongBlockTypeError(
                data.block_id,
                expected=BlogPostBlockType.HTML.value,
                actual=block.type.value,
            )

        sanitized = await self._html_sanitizer.sanitize(data.html)
        block.update_html(BlogHtmlContent(sanitized))
        await self._block_gateway.update_html(block)
        await self._transaction.commit()
