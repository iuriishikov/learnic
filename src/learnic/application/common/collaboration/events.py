from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


class ContentEventKind(StrEnum):
    """Discriminator for collaborative content events.

    Events are coarse-grained — one per domain mutation, not per
    keystroke. Clients receiving an event update their local tree
    by either applying the small ``payload`` directly or re-fetching
    the affected sub-tree from REST.
    """

    MODULE_ADDED = "module_added"
    MODULE_RENAMED = "module_renamed"
    MODULE_DESCRIPTION_UPDATED = "module_description_updated"
    MODULES_REORDERED = "modules_reordered"
    MODULE_DELETED = "module_deleted"

    LESSON_ADDED = "lesson_added"
    LESSON_RENAMED = "lesson_renamed"
    LESSON_MOVED = "lesson_moved"
    LESSONS_REORDERED = "lessons_reordered"
    LESSON_DELETED = "lesson_deleted"

    BLOCK_ADDED = "block_added"
    BLOCK_UPDATED = "block_updated"
    BLOCK_DELETED = "block_deleted"
    BLOCKS_REORDERED = "blocks_reordered"

    RELEASE_CREATED = "release_created"
    DRAFT_RESET = "draft_reset"


@dataclass(slots=True, frozen=True)
class ContentEvent:
    """A single collaborative-edit event for a course product.

    Carries enough id-level info for the client to update its
    local state without refetching for trivial changes (e.g.
    ``module_renamed`` carries the new title), or to know what
    to refetch for non-trivial ones (e.g. ``block_updated`` only
    carries ``block_id`` + ``type`` — content is fetched via
    REST). Keeping payloads small makes the channel cheap to
    fan-out.
    """

    kind: ContentEventKind
    product_id: ProductID
    actor_id: UserID
    payload: dict[str, Any]
    occurred_at: datetime
