from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    InvalidReorderError,
)
from learnic.application.common.persistence.blog_post import BlogPostGateway
from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.ids import BlogPostBlockID


@dataclass(slots=True, frozen=True)
class ReorderBlogPostBlocksCommand:
    post_id: BlogPostID
    ordered_ids: list[BlogPostBlockID]


@final
class ReorderBlogPostBlocksCommandHandler:
    """Replace block ordering inside a post atomically.

    ``ordered_ids`` must equal the post's existing block set exactly
    (irrespective of block type — all types share one position-space
    within a post); anything else is an :class:`InvalidReorderError`.
    """

    def __init__(
        self,
        transaction: Transaction,
        blog_post_gateway: BlogPostGateway,
        block_gateway: BlogPostBlockGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._blog_post_gateway: Final = blog_post_gateway
        self._block_gateway: Final = block_gateway

    async def run(self, data: ReorderBlogPostBlocksCommand) -> None:
        post = await self._blog_post_gateway.with_id(data.post_id)
        if post is None:
            raise EntityNotFoundError(data.post_id)

        await self._block_gateway.lock_for_post(data.post_id)
        existing = await self._block_gateway.list_for_post(data.post_id)
        existing_ids = {b.oid for b in existing}
        provided_ids = set(data.ordered_ids)
        if (
            len(data.ordered_ids) != len(provided_ids)
            or provided_ids != existing_ids
        ):
            raise InvalidReorderError

        await self._block_gateway.reorder(data.post_id, data.ordered_ids)
        await self._transaction.commit()
