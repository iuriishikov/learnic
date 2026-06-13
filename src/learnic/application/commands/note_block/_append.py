"""Shared orchestration for the simple ``add_*`` block handlers.

Every typed add handler resolves the parent lesson + product,
authorises ``EDIT_LESSONS``, locks the lesson's block set, enforces
the per-lesson cap and computes the next position identically, then
commits and publishes a ``BlockAddedPayload``. That orchestration —
the single authoritative home of the append policy (lock granularity,
cap enforcement, positioning, the publish contract) — lives here so
each typed handler keeps only its value-object construction and its
one ``block_gateway.add_<type>(...)`` call.

The file / video-file / photo-collage add handlers deliberately do
NOT use these helpers: they interleave an upload + storage-quota
check between authorisation and positioning and publish an extra
``usage_changed`` event, so their flow legitimately differs (see the
note in each of those modules).
"""

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    BlockAddedPayload,
    ContentEventBus,
    publish_content_event,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_block import (
    LessonBlockGateway,
)
from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.common.limits import LESSON_BLOCK_LIMIT
from learnic.entities.note_block.models import LessonBlock
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


async def prepare_block_append(
    *,
    actor_id: UserID,
    lesson_id: NoteLessonID,
    authorizer: Authorizer,
    product_gateway: ProductGateway,
    lesson_gateway: NoteLessonGateway,
    block_gateway: LessonBlockGateway,
) -> tuple[NoteLesson, int]:
    """Resolve + authorise the parent and reserve the next block slot.

    Args:
        actor_id: The acting user.
        lesson_id: Lesson the block is being appended to.
        authorizer: Permission checker.
        product_gateway: Resolves the owning product.
        lesson_gateway: Resolves the parent lesson.
        block_gateway: Locks the lesson's block set and lists it.

    Returns:
        The loaded :class:`NoteLesson` and the next free position.

    Raises:
        EntityNotFoundError: Lesson or its product does not exist.
        ResourceLimitReachedError: The lesson already holds
            ``LESSON_BLOCK_LIMIT`` blocks.
    """
    lesson = await lesson_gateway.with_id(lesson_id)
    if lesson is None:
        raise EntityNotFoundError(lesson_id)
    product = await product_gateway.with_id(lesson.product_id)
    if product is None:
        raise EntityNotFoundError(lesson.product_id)
    await authorizer.require(
        actor_id,
        AuthzTarget.for_product(lesson.product_id),
        Permission.EDIT_LESSONS,
    )

    await block_gateway.lock_for_lesson(lesson_id)
    existing = await block_gateway.list_for_lesson(lesson_id)
    LESSON_BLOCK_LIMIT.ensure(len(existing))
    next_position = max((b.position for b in existing), default=-1) + 1
    return lesson, next_position


async def commit_and_publish_added(
    *,
    transaction: Transaction,
    event_bus: ContentEventBus,
    lesson_id: NoteLessonID,
    block: LessonBlock,
    product_id: ProductID,
    actor_id: UserID,
) -> None:
    """Commit the append transaction and broadcast the new block."""
    await transaction.commit()
    await publish_content_event(
        event_bus,
        payload=BlockAddedPayload.from_entity(
            lesson_id=lesson_id,
            block=block,
        ),
        product_id=product_id,
        actor_id=actor_id,
    )
