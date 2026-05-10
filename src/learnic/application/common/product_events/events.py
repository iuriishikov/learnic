from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


class ProductEventKind(StrEnum):
    """Discriminator for product-level events.

    These events cover product metadata mutations (name, description,
    duration, cover, status), webinar defaults, Q&A entries, and
    collaboration lifecycle (invite / accept / revoke / grants
    update) — i.e. everything an author or collaborator can change
    from the product screens that is not course-content (modules /
    lessons / blocks / releases). Cohorts (and their schedules /
    sessions) live under their own management screens and are
    intentionally not covered yet.
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

    WEBINAR_DEFAULTS_UPDATED = "webinar_defaults_updated"

    QA_ADDED = "qa_added"
    QA_QUESTION_CHANGED = "qa_question_changed"
    QA_ANSWER_CHANGED = "qa_answer_changed"
    QA_REORDERED = "qa_reordered"
    QA_DELETED = "qa_deleted"

    COLLABORATION_INVITED = "collaboration_invited"
    COLLABORATION_ACCEPTED = "collaboration_accepted"
    COLLABORATION_DECLINED = "collaboration_declined"
    COLLABORATION_REVOKED = "collaboration_revoked"
    COLLABORATION_GRANTS_UPDATED = "collaboration_grants_updated"


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


def make_collaboration_payload(
    *,
    collaboration_id: ProductCollaborationID,
    collaborator_id: UserID | None = None,
    invited_email: str | None = None,
) -> dict[str, Any]:
    """Build the standard payload shape for ``COLLABORATION_*`` kinds.

    Always includes ``collaboration_id``; ``collaborator_id`` is
    present once the invite has been accepted (or for
    ``COLLABORATION_INVITED`` if the invitee was an existing user —
    by-email invites carry ``invited_email`` instead). Either is
    enough for the SPA to identify the affected entry.
    """
    payload: dict[str, Any] = {
        "collaboration_id": str(collaboration_id),
    }
    if collaborator_id is not None:
        payload["collaborator_id"] = str(collaborator_id)
    if invited_email is not None:
        payload["invited_email"] = invited_email
    return payload
