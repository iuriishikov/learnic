import uuid
from dataclasses import dataclass
from datetime import datetime

from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.billing.ids import PlanCode
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ProductRefView:
    """Lightweight product reference embedded in collaboration views.

    Carries only what the panel needs to render the inline pill
    (``Dashboard 2.0`` in the mock-up). Full fetch goes through
    ``GET /products/{id}`` if the user clicks through.
    """

    oid: ProductID
    name: str


@dataclass(slots=True, frozen=True)
class CollaborationSnapshotView:
    """Live snapshot of the collaboration referenced by an invite notification.

    Embedded inside :class:`InviteSentView` and
    :class:`InviteAcceptedView` and hydrated by the reader through a
    join with ``product_collaborations``. The frontend uses
    :attr:`status` (plus the timestamps) as the single source of
    truth for the Accept / Decline card state — a reload picks up
    the latest collaboration row, so local React state never has
    to ``remember`` whether the invite was already resolved.

    ``None`` only if the underlying collaboration row was deleted
    out of band (it never is in current code — REVOKED / DECLINED
    are terminal but preserved). Treat ``None`` defensively as
    ``unavailable`` on the client.
    """

    status: CollaborationStatus
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    invite_expires_at: datetime | None


@dataclass(slots=True, frozen=True)
class InviteSentView:
    collaboration_id: ProductCollaborationID
    product: ProductRefView
    collaboration: CollaborationSnapshotView | None


@dataclass(slots=True, frozen=True)
class InviteAcceptedView:
    collaboration_id: ProductCollaborationID
    product: ProductRefView
    collaborator: UserRefView
    collaboration: CollaborationSnapshotView | None
    viewer_can_manage_collaborators: bool = False
    """Does the recipient currently hold ``MANAGE_COLLABORATORS`` on
    the product? Resolved at read time so the SPA can hide the
    "revoke" CTA for users who lost the permission since the
    notification was published."""


@dataclass(slots=True, frozen=True)
class InviteDeclinedView:
    collaboration_id: ProductCollaborationID
    product: ProductRefView
    decliner: UserRefView
    collaboration: CollaborationSnapshotView | None
    viewer_can_manage_collaborators: bool = False
    """Does the recipient currently hold ``MANAGE_COLLABORATORS`` on
    the product? Drives the visibility of the "re-invite" CTA — if
    ``False`` the SPA hides the action button regardless of the
    underlying collaboration status."""


@dataclass(slots=True, frozen=True)
class AccessRevokedView:
    """Read-side projection of ``access_revoked`` notifications.

    Sent to a user whose **active** collaboration was revoked. The
    card is intentionally read-only — the recipient lost access to
    the product, so there is no in-app action they can take.
    """

    collaboration_id: ProductCollaborationID
    product: ProductRefView
    revoker: UserRefView


@dataclass(slots=True, frozen=True)
class NewLoginView:
    """Read-side projection of ``new_login`` notifications.

    Sent to the user whenever a successful login lands on their
    account. ``device_label`` is the short human-readable form of
    the User-Agent (e.g. ``"Chrome on macOS"``) and is what the
    panel surfaces by default. ``user_agent`` and ``ip_address``
    are kept around for a future "see details" expander.

    ``session_id`` mirrors the refresh-token ``family_id`` minted
    at login. It is the identifier the panel passes to
    ``DELETE /auth/sessions/{session_id}`` for the inline
    "Logout from this device" CTA on the security card.

    ``session_revoked`` is the live state of that refresh-token
    family at read time: ``True`` when the family has been
    revoked OR has expired OR no longer exists, ``False`` when a
    matching active row is present. The panel uses it to derive
    the initial CTA state across reloads — the local
    "I just clicked Logout" status doesn't survive a refresh, but
    this flag does.
    """

    device_label: str | None
    user_agent: str | None
    ip_address: str | None
    session_id: uuid.UUID
    session_revoked: bool


@dataclass(slots=True, frozen=True)
class StorageQuotaWarningView:
    """Read-side projection of ``storage_quota_warning`` notifications.

    Carries the snapshot of the user's quota state at the moment
    the breach was detected. Numbers may drift before the panel is
    opened — the SPA renders them as historical ("at the time of
    detection") and re-fetches live state from
    ``GET /users/me/subscription`` if it needs the current value.
    """

    plan_code: PlanCode
    over_bytes: int
    plan_limit_bytes: int
    grace_until: datetime


@dataclass(slots=True, frozen=True)
class StorageQuotaEnforcedView:
    """Read-side projection of ``storage_quota_enforced`` notifications.

    Records the outcome of one enforcement pass. The deletions are
    soft (``files.deleted_at = now()``) so a support flow can
    recover them while the file-lifecycle worker has not hard-
    deleted them yet.
    """

    plan_code: PlanCode
    deleted_files_count: int
    freed_bytes: int


NotificationDetailsView = (
    InviteSentView
    | InviteAcceptedView
    | InviteDeclinedView
    | AccessRevokedView
    | NewLoginView
    | StorageQuotaWarningView
    | StorageQuotaEnforcedView
)


@dataclass(slots=True, frozen=True)
class NotificationView:
    """Read-side projection of a notification with hydrated refs.

    What goes over the wire — both REST list responses and the
    WebSocket push payload. Producers (command handlers) build it
    once after commit and hand it to :class:`NotificationPublisher`;
    the reader rebuilds it from joined Postgres rows for the list
    endpoint.
    """

    oid: NotificationID
    recipient_id: UserID
    kind: NotificationKind
    category: NotificationCategory
    actor: UserRefView | None
    created_at: datetime
    read_at: datetime | None
    details: NotificationDetailsView


@dataclass(slots=True, frozen=True)
class CategoryCount:
    category: NotificationCategory
    total: int
    unread: int


@dataclass(slots=True, frozen=True)
class NotificationCounters:
    """Per-tab counts plus the ``view-all`` aggregate.

    Drives the badges in the segmented control (``View all 10`` /
    ``Invites 12``) and the unread-dot on the bell icon
    (``unread > 0``).
    """

    total: int
    unread: int
    by_category: tuple[CategoryCount, ...]


@dataclass(slots=True, frozen=True)
class NotificationListPage:
    """Cursor pagination envelope for the list query.

    ``next_cursor`` is the ``created_at`` of the last item, ISO
    formatted; ``None`` when the page is the tail. The reader sorts
    by ``(created_at desc, oid)`` to keep ordering stable on ties.
    """

    items: tuple[NotificationView, ...]
    next_cursor: str | None
