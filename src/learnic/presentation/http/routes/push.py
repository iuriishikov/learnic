"""Web Push HTTP routes — public VAPID key + per-user subscriptions.

The settings flow on the frontend uses these routes to:

- ``GET /web-push/vapid-public-key`` — fetch the VAPID public key
  required to subscribe in the browser. Public, no auth.
- ``POST /users/me/web-push/subscriptions`` — register or refresh a
  ``PushSubscription`` for the current user-device.
- ``DELETE /users/me/web-push/subscriptions`` — drop a subscription
  by endpoint (idempotent).
- ``GET /users/me/web-push/subscriptions`` — list devices for the
  settings UI (one card per registered browser).
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

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
from learnic.entities.push_subscription.models import PushSubscription
from learnic.infrastructure.configs import WebPushConfig
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import AUTHENTICATED_MAP
from learnic.presentation.http.common.router import DishkaErrorAwareRoute


_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]


public_router = ErrorAwareRouter(
    prefix="/web-push",
    tags=["Web Push"],
    route_class=DishkaErrorAwareRoute,
)

me_router = ErrorAwareRouter(
    prefix="/users/me/web-push",
    tags=["Web Push"],
    route_class=DishkaErrorAwareRoute,
)


# ---------------------------- request schemas --------------------------- #


class WebPushSubscribeRequest(BaseModel):
    """Body of ``POST /users/me/web-push/subscriptions``.

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


class WebPushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)


# ---------------------------- response schemas -------------------------- #


class VapidKeySchema(BaseModel):
    """Public VAPID identifier handed to the browser at subscribe-time.

    The ``public_key`` is the URL-safe Base64 encoding of the raw
    P-256 EC point; the SPA decodes it to a ``Uint8Array`` and
    passes it to ``PushManager.subscribe`` as
    ``applicationServerKey``.
    """

    public_key: str


class WebPushSubscriptionSchema(BaseModel):
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


class WebPushSubscriptionsListSchema(BaseModel):
    items: list[WebPushSubscriptionSchema]


# -------------------------------- routes -------------------------------- #


@public_router.get(
    "/vapid-public-key",
    summary="Return the VAPID public key for browser subscriptions",
    operation_id="getWebPushVapidPublicKey",
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
    operation_id="subscribeWebPush",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def subscribe_web_push(
    request: Request,
    body: WebPushSubscribeRequest,
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
    operation_id="unsubscribeWebPush",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def unsubscribe_web_push(
    request: Request,
    body: WebPushUnsubscribeRequest,
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
    operation_id="listMyWebPushSubscriptions",
    response_model=WebPushSubscriptionsListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_MAP,
)
async def list_my_web_push_subscriptions(
    request: Request,
    interactor: FromDishka[ListMyPushSubscriptionsQueryHandler],
    auth: FromDishka[Authenticator],
) -> WebPushSubscriptionsListSchema:
    """Return the caller's registered subscriptions.

    Drives the "Devices" list in the settings UI.

    Args:
        request: Source of the access cookie.
        interactor: Injected list-my query handler.
        auth: Injected authenticator.

    Returns:
        :class:`WebPushSubscriptionsListSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    items = await interactor.run(
        ListMyPushSubscriptionsQuery(actor_id=ctx.user_id),
    )
    return WebPushSubscriptionsListSchema(
        items=[
            WebPushSubscriptionSchema.from_entity(item) for item in items
        ],
    )
