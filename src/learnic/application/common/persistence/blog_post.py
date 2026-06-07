from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileView
from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID


@dataclass(slots=True, frozen=True)
class BlogHtmlBlockView:
    """Read-side projection of an HTML blog block."""

    type: Literal[BlogPostBlockType.HTML]
    oid: BlogPostBlockID
    position: int
    html: str


@dataclass(slots=True, frozen=True)
class BlogImageBlockView:
    """Read-side projection of an image blog block.

    ``file`` carries a resolved :class:`FileView` with a short-lived
    presigned URL the SPA renders directly via ``<img>``. It is
    nullable so a block that outlived its backing file degrades to a
    missing-image placeholder rather than disappearing.
    """

    type: Literal[BlogPostBlockType.IMAGE]
    oid: BlogPostBlockID
    position: int
    file: FileView | None
    caption: str | None


@dataclass(slots=True, frozen=True)
class BlogVideoBlockView:
    """Read-side projection of a video blog block.

    ``file`` carries a resolved :class:`FileView` with a presigned URL
    the SPA plays via ``<video>``. Nullable for the same reason as
    :class:`BlogImageBlockView`.
    """

    type: Literal[BlogPostBlockType.VIDEO]
    oid: BlogPostBlockID
    position: int
    file: FileView | None
    title: str | None


BlogPostBlockView = BlogHtmlBlockView | BlogImageBlockView | BlogVideoBlockView


@dataclass(slots=True, frozen=True)
class BlogPostSummaryView:
    """Lightweight blog-post projection for list endpoints (no blocks).

    ``cover`` is the resolved cover image (presigned URL) or ``None``
    when the post has no cover attached — the SPA falls back to a
    brand placeholder. Resolved by the reader so list endpoints carry
    the cover without a per-post follow-up call.
    """

    oid: BlogPostID
    title: str
    slug: str
    status: BlogPostStatus
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    cover: FileView | None


@dataclass(slots=True, frozen=True)
class BlogPostAuthorView:
    """Resolved author byline for a post's public page.

    ``name`` and ``avatar`` come from the post's ``created_by``
    administrator (``avatar`` is a resolved :class:`FileView` with a
    presigned URL). The whole view is ``None`` on the post when the
    creating admin's account is gone (``created_by`` was ``SET NULL``).
    """

    name: str
    avatar: FileView | None


@dataclass(slots=True, frozen=True)
class BlogPostView:
    """Full blog-post projection: metadata plus the ordered block list.

    Block files are resolved to :class:`FileView` (presigned URL) by
    the reader, so the query handler stays trivial and the SPA renders
    media without a follow-up call. ``cover`` follows the same rule —
    a resolved :class:`FileView` or ``None`` when no cover is set.
    ``author`` is the resolved byline (creator name + avatar), or
    ``None`` when the creating admin's account is gone. ``topic`` is the
    optional category label shown above the title.
    """

    oid: BlogPostID
    title: str
    slug: str
    status: BlogPostStatus
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    cover: FileView | None
    subtitle: str | None
    topic: str | None
    author: BlogPostAuthorView | None
    blocks: list[BlogPostBlockView]


@dataclass(slots=True, frozen=True)
class BlogPostListFilters:
    """Filter set for blog-post list/count queries.

    ``status=None`` returns posts in every status (admin listing);
    a concrete status narrows to that lifecycle state (the public
    catalog passes ``PUBLISHED``).
    """

    status: BlogPostStatus | None = None


class BlogPostOrder(StrEnum):
    """Sort order for blog-post list queries (all newest-first).

    - ``CREATED_DESC`` — most recently *created* first. Used by the
      admin listing, which mixes drafts (no publish date) and
      published posts and wants a stable, predictable order.
    - ``PUBLISHED_DESC`` — most recently *published* first (then
      ``created_at`` as a tiebreak). Used by the public index so a
      post drafted long ago but published recently surfaces at the
      top, the way a reader expects "newest posts" to behave.
    """

    CREATED_DESC = "created_desc"
    PUBLISHED_DESC = "published_desc"


class BlogPostGateway(Protocol):
    """Write-side gateway for the :class:`BlogPost` aggregate root."""

    async def with_id(self, oid: BlogPostID) -> BlogPost | None: ...

    async def slug_exists(self, slug: str) -> bool:
        """Return whether any post already uses ``slug``.

        Used by create / change-slug handlers to reject duplicates
        with a precise 409 before hitting the unique-index violation.
        """
        ...

    async def delete(self, post: BlogPost) -> None:
        """Hard-delete the post; child blocks cascade at the DB level."""
        ...


class BlogPostReader(Protocol):
    """Read-side queries returning wire-ready blog-post projections.

    The reader signs presigned URLs for media blocks itself (it is
    constructed with a ``FileStorage``), so callers receive a
    fully-resolved :class:`BlogPostView` / list of
    :class:`BlogPostSummaryView`.
    """

    async def with_id(self, oid: BlogPostID) -> BlogPostView | None:
        """Return any post by id with its blocks (admin surface)."""
        ...

    async def published_with_slug(self, slug: str) -> BlogPostView | None:
        """Return a ``PUBLISHED`` post by slug with its blocks (public).

        Drafts are invisible here — a draft slug returns ``None`` so
        the public endpoint answers 404 exactly as it would for an
        unknown slug.
        """
        ...

    async def block_with_id(
        self,
        block_id: BlogPostBlockID,
    ) -> BlogPostBlockView | None:
        """Return a single block view (with presigned media), or ``None``.

        Used by block add/update endpoints to return the freshly
        written block to the SPA without a full-post refetch.
        """
        ...

    async def list(
        self,
        filters: BlogPostListFilters,
        pagination: Pagination,
        order: BlogPostOrder = BlogPostOrder.CREATED_DESC,
    ) -> list[BlogPostSummaryView]:
        """Return a page of post summaries in the requested order.

        ``order`` defaults to ``CREATED_DESC`` (newest created first);
        the public index passes ``PUBLISHED_DESC`` so the feed is
        ordered by publication date.
        """
        ...

    async def count(self, filters: BlogPostListFilters) -> int:
        """Return the total number of posts matching ``filters``."""
        ...
