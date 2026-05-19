import uuid
from dataclasses import dataclass
from datetime import datetime

from learnic.entities.billing.ids import PlanCode
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


@dataclass(slots=True)
class NewLoginDetails(NotificationDetails):
    """Body for the ``new_login`` notification.

    Emitted when a successful login lands on the user's account.
    ``device_label`` is the short human-readable string the
    auth flow already derives from the User-Agent for the active
    sessions list (e.g. ``"Chrome on macOS"``); ``user_agent`` is
    the raw header truncated to the column width and kept around
    so a future "see details" expander can render the full string
    without another fetch. ``ip_address`` is captured for the
    same reason — all three fields are nullable because non-browser
    clients (or legacy callers) may not provide them.

    ``session_id`` is the refresh-token ``family_id`` minted at
    login time. It is the same identifier the active-sessions
    list uses so the panel can render a "Logout from this device"
    CTA that hits ``DELETE /auth/sessions/{session_id}``. Carrying
    it on the notification means a recipient who spots a hostile
    login can revoke that session without leaving the panel.
    """

    device_label: str | None
    user_agent: str | None
    ip_address: str | None
    session_id: uuid.UUID


@dataclass(slots=True)
class StorageQuotaWarningDetails(NotificationDetails):
    """Body for the ``storage_quota_warning`` notification.

    Emitted by the reconciliation job when an author's used bytes
    first exceed their plan cap. Carries the snapshot the SPA needs
    to render a precise message — "You are over the FREE 2 GB cap
    by 1.4 GB. Free up space before <grace_until> or we will delete
    the most recently uploaded files." ``plan_code`` reflects the
    plan at detection, not at the moment the user opens the panel
    — drift between the two is informational copy, not an action
    decision.
    """

    plan_code: PlanCode
    over_bytes: int
    plan_limit_bytes: int
    grace_until: datetime


@dataclass(slots=True)
class StorageQuotaEnforcedDetails(NotificationDetails):
    """Body for the ``storage_quota_enforced`` notification.

    Emitted after the reconciliation job has soft-deleted the
    overflow because the grace period expired without the user
    bringing their usage under cap. ``deleted_files_count`` and
    ``freed_bytes`` describe what was actually removed in this
    enforcement pass; ``plan_code`` is informational. The panel
    card is read-only — recovery (un-delete) is a support flow
    while the soft-deleted rows still exist; eventual hard-delete
    by the file-lifecycle worker is irreversible.
    """

    plan_code: PlanCode
    deleted_files_count: int
    freed_bytes: int
