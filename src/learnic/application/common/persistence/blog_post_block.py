from typing import Protocol

from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import (
    BlogHtmlBlock,
    BlogImageBlock,
    BlogPostBlock,
    BlogVideoBlock,
)


class BlogPostBlockGateway(Protocol):
    """Write-side gateway for blog-post blocks.

    Like lesson blocks, blog blocks use joined inheritance (parent
    ``blog_post_blocks`` + per-type child tables), which is awkward in
    SQLAlchemy imperative mapping — so this gateway works through Core:
    each ``add_*`` / ``update_*`` method issues the parent + child
    statements explicitly inside the request transaction.
    """

    async def with_id(self, oid: BlogPostBlockID) -> BlogPostBlock | None: ...

    async def list_for_post(
        self,
        post_id: BlogPostID,
    ) -> list[BlogPostBlock]:
        """Return all blocks of a post, ordered by position ascending."""
        ...

    async def lock_for_post(self, post_id: BlogPostID) -> None:
        """Take a transaction-scoped advisory lock on ``post_id``.

        Position assignment (``add_*``) and ``reorder`` read the post's
        blocks, compute new ``position`` values, then write — a
        check-then-act two concurrent editors could interleave into
        colliding positions. Call this FIRST in every position-mutating
        handler so those operations serialize per post; the lock
        auto-releases on COMMIT / ROLLBACK.
        """
        ...

    async def add_html(self, block: BlogHtmlBlock) -> None: ...

    async def update_html(self, block: BlogHtmlBlock) -> None: ...

    async def add_image(self, block: BlogImageBlock) -> None: ...

    async def update_image(self, block: BlogImageBlock) -> None: ...

    async def add_video(self, block: BlogVideoBlock) -> None: ...

    async def update_video(self, block: BlogVideoBlock) -> None: ...

    async def delete(self, oid: BlogPostBlockID) -> None: ...

    async def reorder(
        self,
        post_id: BlogPostID,
        ordered_ids: list[BlogPostBlockID],
    ) -> None:
        """Atomic full-reorder of all blocks within a post."""
        ...
