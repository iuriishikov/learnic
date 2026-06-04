from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import (
    BlogPostReader,
    BlogPostView,
)
from learnic.entities.blog_post.ids import BlogPostID


@dataclass(slots=True, frozen=True)
class GetBlogPostQuery:
    post_id: BlogPostID


@final
class GetBlogPostQueryHandler:
    """Fetch a single blog post by id, in any status (admin surface).

    Returns the full :class:`BlogPostView` including the ordered block
    list with presigned media URLs already resolved.
    """

    def __init__(self, reader: BlogPostReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetBlogPostQuery) -> BlogPostView:
        view = await self._reader.with_id(data.post_id)
        if view is None:
            raise EntityNotFoundError(data.post_id)
        return view
