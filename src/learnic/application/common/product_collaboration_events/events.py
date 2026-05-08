from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


class CollaborationEventKind(StrEnum):
    """Discriminator for collaboration-lifecycle events.

    These events are published by the collaboration command handlers
    after their request transaction commits, so subscribers never
    observe a rolled-back invite/accept/revoke. The event stream
    answers "who has access to my product right now" — clients
    subscribed to the channel re-render the collaborators list and,
    for the affected user, re-fetch effective permissions to update
    UI gating.
    """

    INVITED = "invited"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    GRANTS_UPDATED = "grants_updated"


@dataclass(slots=True, frozen=True)
class CollaborationEvent:
    """A single collaboration-lifecycle event.

    ``payload`` carries id-level information (``collaboration_id``
    always; ``collaborator_id`` when known). The client uses
    ``kind`` + ``collaboration_id`` to invalidate cached lists; for
    permission-affecting events (``GRANTS_UPDATED``, ``REVOKED``)
    the affected user should also call
    ``GET /products/{id}/collaborations/me/permissions`` to refresh
    UI gating.
    """

    kind: CollaborationEventKind
    product_id: ProductID
    actor_id: UserID
    payload: dict[str, Any]
    occurred_at: datetime

    @staticmethod
    def make_payload(
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID | None = None,
        invited_email: str | None = None,
    ) -> dict[str, Any]:
        """Build the standard ``payload`` shape used by every kind.

        Always includes ``collaboration_id``; ``collaborator_id`` is
        present once the invite has been accepted (or for
        ``INVITED`` if the invitee was an existing user — by-email
        invites carry ``invited_email`` instead). Either is enough
        for the SPA to identify the affected entry.
        """
        payload: dict[str, Any] = {
            "collaboration_id": str(collaboration_id),
        }
        if collaborator_id is not None:
            payload["collaborator_id"] = str(collaborator_id)
        if invited_email is not None:
            payload["invited_email"] = invited_email
        return payload
