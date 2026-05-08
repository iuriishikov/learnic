from dataclasses import dataclass

from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True)
class NotificationDetails:
    """Polymorphic body of a notification.

    Each concrete subclass corresponds to a row in a dedicated
    ``notification_<kind>`` subtype table. Subtype tables share the
    notification id with the parent ``notification`` row through a
    composite ``(notification_id, kind)`` foreign key — that
    enforces "comment-shaped subtype attaches only to a comment-kind
    notification" at the database level.
    """


@dataclass(slots=True)
class InviteSentDetails(NotificationDetails):
    """Body for the ``invite_sent`` notification.

    ``collaboration_id`` is enough to render the Accept/Decline
    actions in the panel — they POST to the existing
    ``/collaborations/{id}/accept`` /
    ``/products/{id}/collaborations/me`` endpoints. ``product_id``
    is denormalised so the panel can show the product name without
    a follow-up fetch.
    """

    collaboration_id: ProductCollaborationID
    product_id: ProductID


@dataclass(slots=True)
class InviteAcceptedDetails(NotificationDetails):
    """Body for the ``invite_accepted`` notification.

    Sent to the inviter when the invitee accepts. Carries the
    ``collaborator_id`` so the panel can render the new
    collaborator's avatar and name without re-deriving the
    relationship from the inviter's products list.
    """

    collaboration_id: ProductCollaborationID
    product_id: ProductID
    collaborator_id: UserID
