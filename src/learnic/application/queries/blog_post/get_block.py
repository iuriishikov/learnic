from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import (
    BlogPostBlockView,
    BlogPostReader,
)
from learnic.entities.blog_post_block.ids import BlogPostBlockID


@dataclass(slots=True, frozen=True)
class GetBlogPostBlockQuery:
    block_id: BlogPostBlockID


@final
class GetBlogPostBlockQueryHandler:
    """Fetch a single blog-post block view (with presigned media URL).

    Used by block create/update endpoints to return the written block
    so the SPA can update its cache without refetching the whole post.
    """

    def __init__(self, reader: BlogPostReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetBlogPostBlockQuery) -> BlogPostBlockView:
        view = await self._reader.block_with_id(data.block_id)
        if view is None:
            raise EntityNotFoundError(data.block_id)
        return view
