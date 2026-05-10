"""In-app notification HTTP routes — list, counters, mark-as-read.

The bell + panel UI calls these:

- ``GET /users/me/notifications`` — paginated list, optionally
  filtered by tab (``category``).
- ``GET /users/me/notifications/counters`` — per-tab totals +
  unread for the segmented control and the bell-icon dot.
- ``POST /users/me/notifications/{id}/read`` — flip one card to
  read.
- ``POST /users/me/notifications/read-all`` — the double-check
  icon.

Caller-scoped, so the routes live under ``/users/me/...`` per the
project's URL-hierarchy rule. Real-time deltas flow over
``WS /users/me/notifications`` — see
``## WebSocket channels`` in the OpenAPI ``info.description``.
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.notification.mark_all_as_read import (
    MarkAllNotificationsAsReadCommand,
    MarkAllNotificationsAsReadCommandHandler,
)
from learnic.application.commands.notification.mark_as_read import (
    MarkNotificationAsReadCommand,
    MarkNotificationAsReadCommandHandler,
)
from learnic.application.common.notifications.views import (
    AccessRevokedView,
    CollaborationSnapshotView,
    InviteAcceptedView,
    InviteDeclinedView,
    InviteSentView,
    NotificationCounters,
    NotificationDetailsView,
    NotificationListPage,
    NotificationView,
    ProductRefView,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
)
from learnic.application.queries.notification.get_counters import (
    GetMyNotificationCountersQuery,
    GetMyNotificationCountersQueryHandler,
)
from learnic.application.queries.notification.list_my import (
    ListMyNotificationsQuery,
    ListMyNotificationsQueryHandler,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_MAP,
    AUTHENTICATED_OWNER_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import UserRefSchema

router = ErrorAwareRouter(
    prefix="/users/me/notifications",
    tags=["Notifications"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_NOTIFICATION_ID_PATH: Final = Path(
    description="Target notification UUID.",
    examples=["a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001"],
)


# --------------------------- response schemas -------------------------- #


class ProductRefSchema(BaseModel):
    """Inline product pill rendered next to the notification body."""

    oid: UUID
    name: str

    @classmethod
    def from_view(cls, view: ProductRefView) -> Self:
        return cls(oid=view.oid, name=view.name)


class CollaborationSnapshotSchema(BaseModel):
    """Live snapshot of the collaboration referenced by an invite card.

    Hydrated by the reader through a join with
    ``product_collaborations``. The SPA uses :attr:`status` (plus
    timestamps) as the single source of truth for the Accept /
    Decline UI state — a reload picks up the latest values, so
    local component state never has to remember whether the
    invitation was already resolved.
    """

    status: CollaborationStatus
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    invite_expires_at: datetime | None

    @classmethod
    def from_view(cls, view: CollaborationSnapshotView) -> Self:
        return cls(
            status=view.status,
            accepted_at=view.accepted_at,
            declined_at=view.declined_at,
            revoked_at=view.revoked_at,
            invite_expires_at=view.invite_expires_at,
        )


class InviteSentDetailsSchema(BaseModel):
    type: str = Field(default="invite_sent", description="Discriminator.")
    collaboration_id: UUID
    product: ProductRefSchema
    collaboration: CollaborationSnapshotSchema | None


class InviteAcceptedDetailsSchema(BaseModel):
    type: str = Field(default="invite_accepted", description="Discriminator.")
    collaboration_id: UUID
    product: ProductRefSchema
    collaborator: UserRefSchema
    collaboration: CollaborationSnapshotSchema | None
    viewer_can_manage_collaborators: bool = Field(
        default=False,
        description=(
            "True when the recipient currently holds "
            "`MANAGE_COLLABORATORS` on the product. The SPA hides "
            "the Revoke CTA when False."
        ),
    )


class InviteDeclinedDetailsSchema(BaseModel):
    type: str = Field(default="invite_declined", description="Discriminator.")
    collaboration_id: UUID
    product: ProductRefSchema
    decliner: UserRefSchema
    collaboration: CollaborationSnapshotSchema | None
    viewer_can_manage_collaborators: bool = Field(
        default=False,
        description=(
            "True when the recipient currently holds "
            "`MANAGE_COLLABORATORS` on the product. The SPA hides "
            "the Re-invite CTA when False."
        ),
    )


class AccessRevokedDetailsSchema(BaseModel):
    """Body of an `access_revoked` notification.

    Sent to a user whose **active** collaboration was revoked. The
    card is read-only — the recipient lost access to the product, so
    there is no in-app CTA. `revoker` carries who removed access for
    display.
    """

    type: str = Field(default="access_revoked", description="Discriminator.")
    collaboration_id: UUID
    product: ProductRefSchema
    revoker: UserRefSchema


NotificationDetailsSchema = (
    InviteSentDetailsSchema
    | InviteAcceptedDetailsSchema
    | InviteDeclinedDetailsSchema
    | AccessRevokedDetailsSchema
)


def _snapshot_to_schema(
    view: CollaborationSnapshotView | None,
) -> CollaborationSnapshotSchema | None:
    if view is None:
        return None
    return CollaborationSnapshotSchema.from_view(view)


def _details_to_schema(view: NotificationDetailsView) -> NotificationDetailsSchema:
    if isinstance(view, InviteSentView):
        return InviteSentDetailsSchema(
            collaboration_id=view.collaboration_id,
            product=ProductRefSchema.from_view(view.product),
            collaboration=_snapshot_to_schema(view.collaboration),
        )
    if isinstance(view, InviteAcceptedView):
        return InviteAcceptedDetailsSchema(
            collaboration_id=view.collaboration_id,
            product=ProductRefSchema.from_view(view.product),
            collaborator=UserRefSchema.from_view(view.collaborator),
            collaboration=_snapshot_to_schema(view.collaboration),
            viewer_can_manage_collaborators=(view.viewer_can_manage_collaborators),
        )
    if isinstance(view, InviteDeclinedView):
        return InviteDeclinedDetailsSchema(
            collaboration_id=view.collaboration_id,
            product=ProductRefSchema.from_view(view.product),
            decliner=UserRefSchema.from_view(view.decliner),
            collaboration=_snapshot_to_schema(view.collaboration),
            viewer_can_manage_collaborators=(view.viewer_can_manage_collaborators),
        )
    if isinstance(view, AccessRevokedView):
        return AccessRevokedDetailsSchema(
            collaboration_id=view.collaboration_id,
            product=ProductRefSchema.from_view(view.product),
            revoker=UserRefSchema.from_view(view.revoker),
        )
    raise NotImplementedError(
        f"Unknown notification details view: {type(view).__name__}",
    )


class NotificationSchema(BaseModel):
    """One row in the panel."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001",
                    "kind": "invite_sent",
                    "category": "invites",
                    "actor": {
                        "oid": "550e8400-e29b-41d4-a716-446655440000",
                        "full_name": "Khan Zaid",
                    },
                    "created_at": "2026-05-08T14:22:00+00:00",
                    "read_at": None,
                    "details": {
                        "type": "invite_sent",
                        "collaboration_id": ("b1c2d3e4-5566-7788-99aa-bbccddeeff00"),
                        "product": {
                            "oid": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                            "name": "Blog design",
                        },
                        "collaboration": {
                            "status": "pending_invite",
                            "accepted_at": None,
                            "declined_at": None,
                            "revoked_at": None,
                            "invite_expires_at": ("2026-05-15T14:22:00+00:00"),
                        },
                    },
                },
            ],
        },
    )

    oid: UUID
    kind: NotificationKind
    category: NotificationCategory
    actor: UserRefSchema | None
    created_at: datetime
    read_at: datetime | None
    details: NotificationDetailsSchema

    @classmethod
    def from_view(cls, view: NotificationView) -> Self:
        return cls(
            oid=view.oid,
            kind=view.kind,
            category=view.category,
            actor=(
                UserRefSchema.from_view(view.actor) if view.actor is not None else None
            ),
            created_at=view.created_at,
            read_at=view.read_at,
            details=_details_to_schema(view.details),
        )


class NotificationPageSchema(BaseModel):
    """Cursor-paginated list response."""

    items: list[NotificationSchema]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: NotificationListPage) -> Self:
        return cls(
            items=[NotificationSchema.from_view(v) for v in page.items],
            next_cursor=page.next_cursor,
        )


class CategoryCountSchema(BaseModel):
    category: NotificationCategory
    total: int
    unread: int


class CountersSchema(BaseModel):
    """Counts driving the segmented control and bell badge."""

    total: int
    unread: int
    by_category: list[CategoryCountSchema]

    @classmethod
    def from_view(cls, view: NotificationCounters) -> Self:
        return cls(
            total=view.total,
            unread=view.unread,
            by_category=[
                CategoryCountSchema(
                    category=bucket.category,
                    total=bucket.total,
                    unread=bucket.unread,
                )
                for bucket in view.by_category
            ],
        )


# ------------------------------ routes --------------------------------- #


@router.get(
    "",
    summary="List notifications of the current user",
    operation_id="listMyNotifications",
    response_model=NotificationPageSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def list_mine(
    request: Request,
    interactor: FromDishka[ListMyNotificationsQueryHandler],
    auth: FromDishka[Authenticator],
    category: NotificationCategory | None = Query(
        default=None,
        description=(
            "Tab filter: omit for the `View all` tab, supply "
            "`invites` / `files` / `jobs` / `other` for a specific "
            "tab. Unknown values are rejected by Pydantic."
        ),
    ),
    cursor: str | None = Query(
        default=None,
        description=(
            "Opaque cursor returned in the previous page's "
            "`next_cursor`. Omit for the first page."
        ),
    ),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> NotificationPageSchema:
    """Return the caller's notifications, sorted newest-first.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected list-my-notifications query handler.
        auth: Injected authenticator.
        category: Optional tab filter — omit for the ``View all``
            tab.
        cursor: Opaque pagination cursor from the previous page.
        limit: Page size (``1..MAX_LIMIT``).

    Returns:
        :class:`NotificationPageSchema` with ``items`` and the
        cursor for the next page (``null`` on the tail).

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    page = await interactor.run(
        ListMyNotificationsQuery(
            actor_id=ctx.user_id,
            category=category,
            cursor=cursor,
            limit=limit,
        ),
    )
    return NotificationPageSchema.from_page(page)


@router.get(
    "/counters",
    summary="Count notifications by tab",
    operation_id="getMyNotificationCounters",
    response_model=CountersSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def counters(
    request: Request,
    interactor: FromDishka[GetMyNotificationCountersQueryHandler],
    auth: FromDishka[Authenticator],
) -> CountersSchema:
    """Return per-tab totals and unread counts for the caller.

    Drives the segmented control's badges (``View all 10`` /
    ``Invites 12``) and the dot on the bell icon (``unread > 0``).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected counters query handler.
        auth: Injected authenticator.

    Returns:
        :class:`CountersSchema` with overall ``total`` / ``unread``
        and per-category buckets.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetMyNotificationCountersQuery(actor_id=ctx.user_id),
    )
    return CountersSchema.from_view(view)


@router.post(
    "/{notification_id}/read",
    summary="Mark a notification as read",
    operation_id="markNotificationRead",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def mark_read(
    request: Request,
    interactor: FromDishka[MarkNotificationAsReadCommandHandler],
    auth: FromDishka[Authenticator],
    notification_id: UUID = _NOTIFICATION_ID_PATH,
) -> None:
    """Mark a single notification as read for the caller.

    Idempotent — re-marking an already-read row returns ``204``
    without re-publishing on the WebSocket channel.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected mark-as-read command handler.
        auth: Injected authenticator.
        notification_id: Target notification, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: The notification belongs to a
            different recipient; HTTP 403.
        EntityNotFoundError: Notification id is unknown; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        MarkNotificationAsReadCommand(
            actor_id=ctx.user_id,
            notification_id=NotificationID(notification_id),
        ),
    )


@router.post(
    "/read-all",
    summary="Mark every notification of the current user as read",
    operation_id="markAllNotificationsRead",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def mark_all_read(
    request: Request,
    interactor: FromDishka[MarkAllNotificationsAsReadCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Mark every unread notification of the caller as read.

    The double-check icon in the panel header. Skips the WebSocket
    push when nothing was unread, so a click on an already-empty
    list never nudges other tabs.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected mark-all-read command handler.
        auth: Injected authenticator.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        MarkAllNotificationsAsReadCommand(actor_id=ctx.user_id),
    )
