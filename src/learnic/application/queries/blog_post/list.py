from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.blog_post import (
    BlogPostListFilters,
    BlogPostReader,
    BlogPostSummaryView,
)
from learnic.entities.blog_post.enums import BlogPostStatus


@dataclass(slots=True, frozen=True)
class PaginatedBlogPostsOutput:
    """A page of :class:`BlogPostSummaryView` plus the total match count.

    ``total`` is the count matching the same filter as ``items`` but
    without pagination — the numerator the SPA needs for numbered page
    controls (``ceil(total / limit)``). Routes surface it via the
    ``X-Total-Count`` response header.
    """

    items: list[BlogPostSummaryView]
    total: int


@dataclass(slots=True, frozen=True)
class ListBlogPostsQuery:
    pagination: Pagination
    status: BlogPostStatus | None = None


@final
class ListBlogPostsQueryHandler:
    """List blog posts in any status, newest first (admin surface).

    ``status=None`` returns every post; a concrete status narrows the
    listing to that lifecycle state.
    """

    def __init__(self, reader: BlogPostReader) -> None:
        self._reader: Final = reader

    async def run(self, data: ListBlogPostsQuery) -> PaginatedBlogPostsOutput:
        filters = BlogPostListFilters(status=data.status)
        items = await self._reader.list(filters, data.pagination)
        total = await self._reader.count(filters)
        return PaginatedBlogPostsOutput(items=items, total=total)
