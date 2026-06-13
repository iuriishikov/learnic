"""Shared orchestration for the simple ``update_*`` block handlers.

Every typed update handler loads the block by id, narrows it to its
concrete subtype (raising ``WrongBlockTypeError`` on a mismatch),
resolves the owning product, authorises ``EDIT_LESSONS``, then — after
the type-specific mutation — commits and publishes a
``BlockUpdatedPayload``. That load-and-authorise gate and the
commit-and-publish tail live here so each typed handler keeps only its
value-object construction, its ``block.update_<x>(...)`` mutation and
its one ``block_gateway.update_<type>(...)`` call.

The file / video-file / photo-collage update handlers deliberately do
NOT use these helpers: they re-upload + re-check the storage quota (or
mutate a child-row collage), so their flow legitimately differs.
"""

from typing import TypeVar

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockUpdatedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import LessonBlock
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID

TBlock = TypeVar("TBlock", bound=LessonBlock)


async def load_typed_block_for_edit(
    *,
    block_id: LessonBlockID,
    actor_id: UserID,
    expected_type: BlockType,
    expected_cls: type[TBlock],
    block_gateway: LessonBlockGateway,
    product_gateway: ProductGateway,
    authorizer: Authorizer,
) -> TBlock:
    """Load + type-narrow + authorise a block for an in-place edit.

    Args:
        block_id: The block being edited.
        actor_id: The acting user.
        expected_type: The ``BlockType`` the route expects (for the
            error payload).
        expected_cls: The concrete entity class the block must be.
        block_gateway: Resolves the block.
        product_gateway: Resolves the owning product.
        authorizer: Permission checker.

    Returns:
        The block, narrowed to ``expected_cls``.

    Raises:
        EntityNotFoundError: Block or its product does not exist.
        WrongBlockTypeError: The block is not of ``expected_cls``.
    """
    block = await block_gateway.with_id(block_id)
    if block is None:
        raise EntityNotFoundError(block_id)
    if not isinstance(block, expected_cls):
        raise WrongBlockTypeError(
            block_id,
            expected=expected_type.value,
            actual=block.type.value,
        )
    product = await product_gateway.with_id(block.product_id)
    if product is None:
        raise EntityNotFoundError(block.product_id)
    await authorizer.require(
        actor_id,
        AuthzTarget.for_product(block.product_id),
        Permission.EDIT_LESSONS,
    )
    return block


async def commit_and_publish_updated(
    *,
    transaction: Transaction,
    event_bus: ContentEventBus,
    block: LessonBlock,
    actor_id: UserID,
) -> None:
    """Commit the edit transaction and broadcast the updated block."""
    await transaction.commit()
    await publish_content_event(
        event_bus,
        payload=BlockUpdatedPayload.from_entity(block),
        product_id=block.product_id,
        actor_id=actor_id,
    )
