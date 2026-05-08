from dataclasses import dataclass
from datetime import datetime

from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ActorView:
    """Read-side projection of the user who triggered the notification.

    Embedded inside :class:`NotificationView` so the panel can render
    the avatar row without a follow-up request to ``/users/{id}``.
    Hydrated via a join in the reader; ``None`` for system-generated
    notifications without an actor.
    """

    oid: UserID
    first_name: str
    last_name: str
    patronymic: str | None


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
class InviteSentView:
    collaboration_id: ProductCollaborationID
    product: ProductRefView


@dataclass(slots=True, frozen=True)
class InviteAcceptedView:
    collaboration_id: ProductCollaborationID
    product: ProductRefView
    collaborator: ActorView


NotificationDetailsView = InviteSentView | InviteAcceptedView


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
    actor: ActorView | None
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
