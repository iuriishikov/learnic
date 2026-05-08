from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


class ProductEventKind(StrEnum):
    """Discriminator for product-level events.

    These events cover product metadata mutations (name, description,
    duration, cover, status) and Q&A entries — i.e. everything an
    author can change from the product edit screen that is not
    course-content (modules / lessons / blocks / releases). Webinar
    defaults and cohorts are intentionally not covered yet.
    """

    NAME_CHANGED = "name_changed"
    DESCRIPTION_CHANGED = "description_changed"
    DURATION_CHANGED = "duration_changed"

    COVER_CHANGED = "cover_changed"
    COVER_REMOVED = "cover_removed"

    PUBLISHED = "published"
    ARCHIVED = "archived"
    UNARCHIVED = "unarchived"
    DELETED = "deleted"

    QA_ADDED = "qa_added"
    QA_QUESTION_CHANGED = "qa_question_changed"
    QA_ANSWER_CHANGED = "qa_answer_changed"
    QA_REORDERED = "qa_reordered"
    QA_DELETED = "qa_deleted"


@dataclass(slots=True, frozen=True)
class ProductEvent:
    """A single product-level event.

    Each ``payload`` carries the new value(s) directly so clients
    can apply the change in place without an extra REST round-trip.
    For deletions the payload is empty — the ``kind`` + ``qa_id``
    (or just the product id for ``DELETED``) is enough.
    """

    kind: ProductEventKind
    product_id: ProductID
    actor_id: UserID
    payload: dict[str, Any]
    occurred_at: datetime
