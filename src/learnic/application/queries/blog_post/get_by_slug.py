from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.blog_post import (
    BlogPostReader,
    BlogPostView,
)


@dataclass(slots=True, frozen=True)
class GetPublishedBlogPostBySlugQuery:
    slug: str


@final
class GetPublishedBlogPostBySlugQueryHandler:
    """Fetch a published blog post by slug (public surface).

    Draft posts are invisible: an unknown slug and a draft slug both
    raise :class:`EntityNotFoundError` (HTTP 404) so the public
    endpoint never leaks the existence of unpublished content.
    """

    def __init__(self, reader: BlogPostReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetPublishedBlogPostBySlugQuery,
    ) -> BlogPostView:
        view = await self._reader.published_with_slug(data.slug)
        if view is None:
            raise EntityNotFoundError(data.slug)
        return view
