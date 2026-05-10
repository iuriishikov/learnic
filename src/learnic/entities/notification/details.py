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


@dataclass(slots=True)
class InviteDeclinedDetails(NotificationDetails):
    """Body for the ``invite_declined`` notification.

    Sent to the inviter when the invitee declines a pending invite
    in-app. Carries ``decliner_id`` so the panel can render the
    declining user's avatar and name without re-deriving the
    relationship. ``collaboration_id`` lets the panel offer a
    "re-invite" action that recreates the collaboration with the
    same target and grants.
    """

    collaboration_id: ProductCollaborationID
    product_id: ProductID
    decliner_id: UserID


@dataclass(slots=True)
class AccessRevokedDetails(NotificationDetails):
    """Body for the ``access_revoked`` notification.

    Sent to a collaborator who was kicked from an **active**
    collaboration (status flipped from ``ACTIVE`` to ``REVOKED``).
    Pending-invite revocations are not covered here — they surface
    on the recipient's existing ``invite_sent`` card via the
    snapshot republish, which already flips the row's status to
    ``revoked``.

    Carries ``revoker_id`` so the panel can render who removed
    access; the card is read-only — there is no recovery action
    the recipient can take from here.
    """

    collaboration_id: ProductCollaborationID
    product_id: ProductID
    revoker_id: UserID
