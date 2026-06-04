from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.blog_post import (
    BlogPostListFilters,
    BlogPostOrder,
    BlogPostReader,
)
from learnic.application.queries.blog_post.list import (
    PaginatedBlogPostsOutput,
)
from learnic.entities.blog_post.enums import BlogPostStatus


@dataclass(slots=True, frozen=True)
class ListPublishedBlogPostsQuery:
    pagination: Pagination


@final
class ListPublishedBlogPostsQueryHandler:
    """Public blog index — posts with status ``PUBLISHED``, newest first."""

    def __init__(self, reader: BlogPostReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: ListPublishedBlogPostsQuery,
    ) -> PaginatedBlogPostsOutput:
        filters = BlogPostListFilters(status=BlogPostStatus.PUBLISHED)
        items = await self._reader.list(
            filters,
            data.pagination,
            order=BlogPostOrder.PUBLISHED_DESC,
        )
        total = await self._reader.count(filters)
        return PaginatedBlogPostsOutput(items=items, total=total)
