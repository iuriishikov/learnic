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

Per-kind ``details`` payloads form a Pydantic discriminated
union: each kind contributes one schema with a fixed ``type``
literal, and the unified dict produced by the kind spec's
:meth:`NotificationKindSpec.to_ws_dict` is validated through
the union. Adding a new kind = add one Pydantic schema and
append it to the union; the route dispatch logic does not change.
"""

from datetime import datetime
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from learnic.application.commands.notification.mark_all_as_read import (
    MarkAllNotificationsAsReadCommand,
    MarkAllNotificationsAsReadCommandHandler,
)
from learnic.application.commands.notification.mark_as_read import (
    MarkNotificationAsReadCommand,
    MarkNotificationAsReadCommandHandler,
)
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
)
from learnic.application.common.notifications.views import (
    CollaborationSnapshotView,
    NotificationCounters,
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
from learnic.entities.product_gift.enums import GiftStatus
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
    type: Literal["invite_sent"] = Field(
        default="invite_sent",
        description="Discriminator.",
    )
    collaboration_id: UUID
    product: ProductRefSchema
    collaboration: CollaborationSnapshotSchema | None


class InviteAcceptedDetailsSchema(BaseModel):
    type: Literal["invite_accepted"] = Field(
        default="invite_accepted",
        description="Discriminator.",
    )
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
    type: Literal["invite_declined"] = Field(
        default="invite_declined",
        description="Discriminator.",
    )
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

    type: Literal["access_revoked"] = Field(
        default="access_revoked",
        description="Discriminator.",
    )
    collaboration_id: UUID
    product: ProductRefSchema
    revoker: UserRefSchema


class NewLoginDetailsSchema(BaseModel):
    """Body of a `new_login` notification.

    Sent to the user when a successful login lands on their
    account. ``device_label`` is the short human-readable form of
    the User-Agent (e.g. ``"Chrome on macOS"``) — the panel's
    primary surface for what device was used. ``user_agent`` is
    the full raw header (truncated server-side) and ``ip_address``
    is the source IP, both kept for a future "see details"
    expander. The first three are nullable because non-browser
    clients or legacy callers may not provide them.

    ``session_id`` is the refresh-token ``family_id`` minted by
    the login that triggered this notification. The SPA passes
    it to ``DELETE /auth/sessions/{session_id}`` for the inline
    "Logout from this device" CTA on the security card.
    """

    type: Literal["new_login"] = Field(
        default="new_login",
        description="Discriminator.",
    )
    session_id: UUID = Field(
        description=(
            "Refresh-token ``family_id`` of the session created by "
            "this login. Pass to "
            "``DELETE /auth/sessions/{session_id}`` to revoke that "
            "specific session from the notification card."
        ),
    )
    session_revoked: bool = Field(
        description=(
            "Live state of the session at read time. ``True`` when "
            "the refresh-token family has been revoked, has expired, "
            "or no longer exists; ``False`` when an active row is "
            "still present. The SPA derives the initial state of "
            'the "Logout from this device" CTA from this flag so '
            "the button reflects reality across reloads."
        ),
    )
    device_label: str | None = Field(
        default=None,
        description=(
            "Short human-readable label for the device that "
            'performed the login (e.g. ``"Chrome on macOS"``). '
            "Derived heuristically from the User-Agent at the "
            "HTTP boundary."
        ),
    )
    user_agent: str | None = Field(
        default=None,
        description=(
            "Raw User-Agent header, truncated server-side. Use "
            'for a "see details" expander when the short label '
            "is not enough."
        ),
    )
    ip_address: str | None = Field(
        default=None,
        description=(
            "Source IP address captured at login. Honours "
            "``X-Forwarded-For`` / ``X-Real-IP`` so the value "
            "reflects the originating client behind a reverse "
            "proxy."
        ),
    )


class StorageQuotaWarningDetailsSchema(BaseModel):
    """Body of a ``storage_quota_warning`` notification.

    Emitted by the daily reconcile job when an author's used bytes
    first exceed their plan cap. The SPA renders a card like
    "You are over the FREE 2 GB cap by 1.4 GB. Free up space or
    upgrade before <grace_until> or we will delete the most
    recently uploaded files." All four numbers are a **snapshot at
    detection** — for live state the SPA falls back to
    ``GET /users/me/subscription``.
    """

    type: Literal["storage_quota_warning"] = Field(
        default="storage_quota_warning",
        description="Discriminator.",
    )
    plan_code: str = Field(
        description=(
            "Plan of the author at the moment the breach was "
            "detected. Stable token (``FREE`` / ``BETA`` / ...)."
        ),
        examples=["FREE", "BETA"],
    )
    over_bytes: int = Field(
        description=(
            "How many bytes above the plan cap the author was at "
            "detection. Drifts over time as the author uploads / "
            "deletes; treat as historical."
        ),
        examples=[1503238553],
        ge=0,
    )
    plan_limit_bytes: int = Field(
        description="Plan cap captured at detection.",
        examples=[2147483648],
        ge=0,
    )
    grace_until: datetime = Field(
        description=(
            "ISO 8601 timestamp (UTC) — after this point the next "
            "reconcile pass soft-deletes the overflow newest-first "
            "until the author is back under cap. Computed as "
            "``detected_at + OVER_QUOTA_GRACE_PERIOD_DAYS`` and "
            "stable for the lifetime of the breach."
        ),
        examples=["2026-06-03T03:00:00+00:00"],
    )


class StorageQuotaEnforcedDetailsSchema(BaseModel):
    """Body of a ``storage_quota_enforced`` notification.

    Sent after the grace period expired and the reconcile job
    soft-deleted the overflow. The card is informational — files
    in the DB are flagged ``deleted_at != NULL`` and the
    S3-purge worker physically removes the blobs. Recovery is a
    support flow while the rows still exist.
    """

    type: Literal["storage_quota_enforced"] = Field(
        default="storage_quota_enforced",
        description="Discriminator.",
    )
    plan_code: str = Field(
        description="Plan the author was on when enforcement ran.",
        examples=["FREE", "BETA"],
    )
    deleted_files_count: int = Field(
        description=(
            "Number of files soft-deleted in this enforcement pass. "
            "Picked newest-first across the author's notes; files "
            "referenced from older blocks are preserved when the "
            "freed total reaches the overage."
        ),
        examples=[7],
        ge=0,
    )
    freed_bytes: int = Field(
        description=(
            "Total size in bytes of the soft-deleted files. May "
            "exceed the overage at detection time — the loop stops "
            "at the first file whose inclusion crosses the cap."
        ),
        examples=[1610612736],
        ge=0,
    )


class GiftSnapshotSchema(BaseModel):
    """Live snapshot of the gift referenced by a gift card.

    Hydrated by the reader through a join with ``product_gifts``.
    The SPA uses :attr:`status` (plus timestamps) as the single
    source of truth for the Accept / Decline UI state — a reload
    picks up the latest values, so local component state never has
    to remember whether the gift was already resolved. ``None`` when
    the gift row was purged by the nightly expiry sweep; treat as
    ``unavailable``.
    """

    status: GiftStatus
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    invite_expires_at: datetime | None


class GiftReceivedDetailsSchema(BaseModel):
    """Body of a `gift_received` notification.

    Sent to the user who was gifted product access. The card renders
    Accept / Decline actions that POST to ``/gifts/{id}/accept`` and
    ``/gifts/{id}/decline``. Use `gift.status` to derive the initial
    button state across reloads.
    """

    type: Literal["gift_received"] = Field(
        default="gift_received",
        description="Discriminator.",
    )
    gift_id: UUID
    product: ProductRefSchema
    gift: GiftSnapshotSchema | None


class GiftAcceptedDetailsSchema(BaseModel):
    """Body of a `gift_accepted` notification.

    Sent to the gifter when the recipient accepts. `recipient`
    carries the accepting user for display.
    """

    type: Literal["gift_accepted"] = Field(
        default="gift_accepted",
        description="Discriminator.",
    )
    gift_id: UUID
    product: ProductRefSchema
    recipient: UserRefSchema
    gift: GiftSnapshotSchema | None


class GiftDeclinedDetailsSchema(BaseModel):
    """Body of a `gift_declined` notification.

    Sent to the gifter when the recipient declines a pending gift.
    `decliner` carries the declining user for display.
    """

    type: Literal["gift_declined"] = Field(
        default="gift_declined",
        description="Discriminator.",
    )
    gift_id: UUID
    product: ProductRefSchema
    decliner: UserRefSchema
    gift: GiftSnapshotSchema | None


NotificationDetailsSchema = Annotated[
    InviteSentDetailsSchema
    | InviteAcceptedDetailsSchema
    | InviteDeclinedDetailsSchema
    | AccessRevokedDetailsSchema
    | NewLoginDetailsSchema
    | StorageQuotaWarningDetailsSchema
    | StorageQuotaEnforcedDetailsSchema
    | GiftReceivedDetailsSchema
    | GiftAcceptedDetailsSchema
    | GiftDeclinedDetailsSchema,
    Field(discriminator="type"),
]

_DETAILS_ADAPTER: Final[TypeAdapter[NotificationDetailsSchema]] = TypeAdapter(
    NotificationDetailsSchema,
)


def _details_from_view(
    view: NotificationView,
    registry: NotificationKindRegistry,
) -> NotificationDetailsSchema:
    """Validate the spec's WS dict through the discriminated union.

    The kind spec produces the same wire dict for both REST and WS
    (:meth:`NotificationKindSpec.to_ws_dict`); the union picks the
    right Pydantic model by ``type`` and validates the payload.
    """
    spec = registry.by_view(view.details)
    payload = {"type": spec.kind.value, **spec.to_ws_dict(view.details)}
    return _DETAILS_ADAPTER.validate_python(payload)


class NotificationSchema(BaseModel):
    """One row in the panel."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001",
                    "kind": "invite_sent",
                    "category": "teaching",
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
    def from_view(
        cls,
        view: NotificationView,
        registry: NotificationKindRegistry,
    ) -> Self:
        return cls(
            oid=view.oid,
            kind=view.kind,
            category=view.category,
            actor=(
                UserRefSchema.from_view(view.actor) if view.actor is not None else None
            ),
            created_at=view.created_at,
            read_at=view.read_at,
            details=_details_from_view(view, registry),
        )


class NotificationPageSchema(BaseModel):
    """Cursor-paginated list response."""

    items: list[NotificationSchema]
    next_cursor: str | None

    @classmethod
    def from_page(
        cls,
        page: NotificationListPage,
        registry: NotificationKindRegistry,
    ) -> Self:
        return cls(
            items=[NotificationSchema.from_view(v, registry) for v in page.items],
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
    registry: FromDishka[NotificationKindRegistry],
    category: NotificationCategory | None = Query(
        default=None,
        description=(
            "Tab filter: omit for the `View all` tab, supply "
            "`teaching` / `learning` / `security` / `files` / "
            "`jobs` / `other` for a specific tab. Unknown values "
            "are rejected by Pydantic."
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
        registry: Injected notification-kind registry; resolves
            per-kind schema dispatch.
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
    return NotificationPageSchema.from_page(page, registry)


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
