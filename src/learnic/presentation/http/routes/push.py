"""Web Push HTTP routes — public VAPID key + per-user subscriptions.

The settings flow on the frontend uses these routes to:

- ``GET /push/vapid-public-key`` — fetch the VAPID public key
  required to subscribe in the browser. Public, no auth.
- ``POST /users/me/push/subscriptions`` — register or refresh a
  ``PushSubscription`` for the current user-device.
- ``DELETE /users/me/push/subscriptions`` — drop a subscription
  by endpoint (idempotent).
- ``GET /users/me/push/subscriptions`` — list devices for the
  settings UI (one card per registered browser).
- ``POST /push/send`` — generic admin/internal endpoint for
  shipping a Web Push to an arbitrary user with full preference
  enforcement at the worker.
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.push.send_to_user import (
    SendPushToUserCommand,
    SendPushToUserCommandHandler,
)
from learnic.application.commands.push.subscribe import (
    SubscribePushCommand,
    SubscribePushCommandHandler,
)
from learnic.application.commands.push.unsubscribe import (
    UnsubscribePushCommand,
    UnsubscribePushCommandHandler,
)
from learnic.application.queries.push.list_my import (
    ListMyPushSubscriptionsQuery,
    ListMyPushSubscriptionsQueryHandler,
)
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.push_subscription.models import PushSubscription
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import WebPushConfig
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import AUTHENTICATED_MAP
from learnic.presentation.http.common.router import DishkaErrorAwareRoute


_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


public_router = ErrorAwareRouter(
    prefix="/push",
    tags=["Web Push"],
    route_class=DishkaErrorAwareRoute,
)

me_router = ErrorAwareRouter(
    prefix="/users/me/push",
    tags=["Web Push"],
    route_class=DishkaErrorAwareRoute,
)


# ---------------------------- request schemas --------------------------- #


class PushSubscribeRequest(BaseModel):
    """Body of ``POST /users/me/push/subscriptions``.

    Mirrors the structure browsers hand to ``PushSubscription
    .toJSON()`` so the frontend can post it almost as-is. Keys are
    URL-safe Base64 strings emitted by the browser; we do not
    re-encode them.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
                    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry...",
                    "auth": "tBHItJI5svbpez7KI4CCXg",
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel ...)",
                },
            ],
        },
    )

    endpoint: str = Field(min_length=1, max_length=2048)
    p256dh: str = Field(min_length=1, max_length=512)
    auth: str = Field(min_length=1, max_length=256)
    user_agent: str | None = Field(default=None, max_length=512)


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)


class SendPushRequest(BaseModel):
    """Body of ``POST /push/send`` — admin-style generic delivery."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "category": "other",
                    "title": "Reminder",
                    "body": "Your draft has not been touched in a week.",
                    "url": "/dashboard",
                },
            ],
        },
    )

    user_id: UUID
    category: NotificationCategory
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    url: str | None = Field(default=None, max_length=2048)
    tag: str | None = Field(default=None, max_length=120)
    icon: str | None = Field(default=None, max_length=2048)


# ---------------------------- response schemas -------------------------- #


class VapidKeySchema(BaseModel):
    """Public VAPID identifier handed to the browser at subscribe-time.

    The ``public_key`` is the URL-safe Base64 encoding of the raw
    P-256 EC point; the SPA decodes it to a ``Uint8Array`` and
    passes it to ``PushManager.subscribe`` as
    ``applicationServerKey``.
    """

    public_key: str


class PushSubscriptionSchema(BaseModel):
    oid: UUID
    endpoint: str
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime

    @classmethod
    def from_entity(cls, entity: PushSubscription) -> Self:
        return cls(
            oid=entity.oid,
            endpoint=entity.endpoint,
            user_agent=entity.user_agent,
            created_at=entity.created_at,
            last_seen_at=entity.last_seen_at,
        )


class PushSubscriptionsListSchema(BaseModel):
    items: list[PushSubscriptionSchema]


# -------------------------------- routes -------------------------------- #


@public_router.get(
    "/vapid-public-key",
    summary="Return the VAPID public key for browser subscriptions",
    operation_id="getVapidPublicKey",
    response_model=VapidKeySchema,
)
async def vapid_public_key(
    config: FromDishka[WebPushConfig],
) -> VapidKeySchema:
    """Return the VAPID public key configured for this environment.

    The frontend reads it once at app boot, decodes it, and feeds
    it to ``PushManager.subscribe`` as ``applicationServerKey``.
    Public on purpose — there's no secret value to protect; the
    public key is by definition shared with browsers.

    Args:
        config: Injected Web Push configuration.

    Returns:
        :class:`VapidKeySchema` carrying the URL-safe Base64 key.
    """
    return VapidKeySchema(public_key=config.vapid_public_key)


@me_router.post(
    "/subscriptions",
    summary="Register or refresh a Web Push subscription",
    operation_id="subscribePush",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def subscribe(
    request: Request,
    body: PushSubscribeRequest,
    interactor: FromDishka[SubscribePushCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Persist the subscription so the worker can deliver pushes.

    Re-subscribe with the same browser → same ``endpoint`` →
    upsert refreshes the keys; new endpoint → new row, same
    user. The handler commits its own transaction so the call
    is safe to retry on partial failures.

    Args:
        request: Source of the access cookie.
        body: Subscription envelope from the browser.
        interactor: Injected subscribe command handler.
        auth: Injected authenticator.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        SubscribePushCommand(
            user_id=ctx.user_id,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
            user_agent=body.user_agent,
        ),
    )


@me_router.delete(
    "/subscriptions",
    summary="Unsubscribe a Web Push endpoint",
    operation_id="unsubscribePush",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def unsubscribe(
    request: Request,
    body: PushUnsubscribeRequest,
    interactor: FromDishka[UnsubscribePushCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Drop the subscription identified by ``endpoint``.

    Idempotent: removing a never-known endpoint returns ``204``
    without a 404 — the SPA may call this on logout regardless
    of whether a subscription was ever stored.

    Args:
        request: Source of the access cookie.
        body: Endpoint to delete.
        interactor: Injected unsubscribe command handler.
        auth: Injected authenticator.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UnsubscribePushCommand(
            user_id=ctx.user_id,
            endpoint=body.endpoint,
        ),
    )


@me_router.get(
    "/subscriptions",
    summary="List my Web Push subscriptions",
    operation_id="listMyPushSubscriptions",
    response_model=PushSubscriptionsListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def list_my(
    request: Request,
    interactor: FromDishka[ListMyPushSubscriptionsQueryHandler],
    auth: FromDishka[Authenticator],
) -> PushSubscriptionsListSchema:
    """Return the caller's registered subscriptions.

    Drives the "Devices" list in the settings UI.

    Args:
        request: Source of the access cookie.
        interactor: Injected list-my query handler.
        auth: Injected authenticator.

    Returns:
        :class:`PushSubscriptionsListSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    items = await interactor.run(
        ListMyPushSubscriptionsQuery(actor_id=ctx.user_id),
    )
    return PushSubscriptionsListSchema(
        items=[PushSubscriptionSchema.from_entity(item) for item in items],
    )


@public_router.post(
    "/send",
    summary="Schedule a Web Push to a specific user with preference check",
    operation_id="sendPush",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def send_to_user(
    request: Request,
    body: SendPushRequest,
    interactor: FromDishka[SendPushToUserCommandHandler],
    auth: FromDishka[Authenticator],
) -> None:
    """Generic delivery endpoint for Web Push to an arbitrary user.

    The worker enforces the recipient's notification preferences
    before emitting any HTTP requests to push services, so a
    stale enqueue can't bypass an opt-out the user just toggled.
    Auth is required; broader access policies (which actor may
    push to which target) are out of scope of this endpoint.

    Args:
        request: Source of the access cookie.
        body: Target user, category and payload fields.
        interactor: Injected send-to-user command handler.
        auth: Injected authenticator.

    Returns:
        ``202 Accepted`` once the task is enqueued.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        SendPushToUserCommand(
            actor_id=ctx.user_id,
            target_user_id=UserID(body.user_id),
            category=body.category,
            title=body.title,
            body=body.body,
            url=body.url,
            tag=body.tag,
            icon=body.icon,
        ),
    )
