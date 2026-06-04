"""Gift HTTP routes — issue, accept, decline, revoke.

Two router objects are exported:

- :data:`product_router` is mounted under
  ``/products/{product_id}/gifts`` and carries the product-scoped
  operations (issue by-user / by-email, list).
- :data:`gift_router` is mounted under ``/gifts`` and carries the
  operations addressed by gift id (get, accept, decline, revoke).
  Accept / decline are the "globally-discoverable invitation"
  exception to the nesting rule (CLAUDE.md core rule 14): the
  recipient reaches them from an email link or in-app card without
  product context.
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.product_gift.accept import (
    AcceptGiftByTokenCommand,
    AcceptGiftByTokenCommandHandler,
)
from learnic.application.commands.product_gift.accept_in_app import (
    AcceptGiftInAppCommand,
    AcceptGiftInAppCommandHandler,
)
from learnic.application.commands.product_gift.decline_in_app import (
    DeclineGiftCommand,
    DeclineGiftCommandHandler,
)
from learnic.application.commands.product_gift.invite_by_email import (
    InviteGiftByEmailCommand,
    InviteGiftByEmailCommandHandler,
)
from learnic.application.commands.product_gift.invite_by_user import (
    InviteGiftByUserCommand,
    InviteGiftByUserCommandHandler,
)
from learnic.application.commands.product_gift.revoke import (
    RevokeGiftCommand,
    RevokeGiftCommandHandler,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.queries.product_gift.get_gift import (
    GetGiftQuery,
    GetGiftQueryHandler,
    ProductGiftOutput,
)
from learnic.application.queries.product_gift.list_for_product import (
    ListProductGiftsQuery,
    ListProductGiftsQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.constants import EMAIL_MAX_LEN
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    GIFT_ACCEPT_MAP,
    GIFT_GET_MAP,
    GIFT_INVITE_MAP,
    GIFT_REVOKE_MAP,
)
from learnic.presentation.http.common.device import client_ip
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import UserSchema

product_router = ErrorAwareRouter(
    prefix="/products/{product_id}/gifts",
    tags=["Gifts"],
    route_class=DishkaErrorAwareRoute,
)

gift_router = ErrorAwareRouter(
    prefix="/gifts",
    tags=["Gifts"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Owning product UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_GIFT_ID_PATH: Final = Path(
    description="Target gift UUID.",
    examples=["a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001"],
)


# --------------------------- request schemas --------------------------- #


class InviteGiftByUserSchema(BaseModel):
    """Body for `POST /products/{product_id}/gifts/by-user`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"user_id": "550e8400-e29b-41d4-a716-446655440000"},
            ],
        },
    )

    user_id: UUID = Field(
        description="UUID of the registered user to gift access to.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class InviteGiftByEmailSchema(BaseModel):
    """Body for `POST /products/{product_id}/gifts/by-email`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"email": "friend@example.com"}]},
    )

    email: str = Field(
        description=(
            "Email address to gift access to. May belong to a user "
            "without an account yet — they accept after registering. "
            f"Max length {EMAIL_MAX_LEN} (`EMAIL_MAX_LEN`)."
        ),
        min_length=3,
        max_length=EMAIL_MAX_LEN,
        examples=["friend@example.com"],
    )


class AcceptGiftSchema(BaseModel):
    """Body for `POST /gifts/{gift_id}/accept-by-token`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"token": "Xt9c...urlsafe"}]},
    )

    token: str = Field(
        description="Plaintext accept token from the gift email link.",
        min_length=1,
        examples=["Xt9c8a2b1f...urlsafe"],
    )


# --------------------------- response schemas -------------------------- #


class CreatedGiftSchema(BaseModel):
    """Response body for gift-issue endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001"}],
        },
    )

    oid: UUID


class GiftSchema(BaseModel):
    """Gift response projection.

    Returned by `GET /gifts/{id}` (the email-link landing page) and
    the product gift list. Carries the product name and gifter
    reference so the landing page renders without extra fetches.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001",
                    "product_id": (
                        "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"
                    ),
                    "product_name": "Python с нуля",
                    "recipient": {
                        "oid": (
                            "550e8400-e29b-41d4-a716-446655440000"
                        ),
                        "full_name": "Lovelace Ada",
                        "email": "a*****a@example.com",
                        "is_verified": False,
                        "avatar": None,
                    },
                    "invited_email": None,
                    "status": "pending_invite",
                    "gifter": {
                        "oid": (
                            "8b1c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"
                        ),
                        "full_name": "Hopper Grace",
                        "email": "g*****r@example.com",
                        "is_verified": True,
                        "avatar": None,
                    },
                    "invite_expires_at": "2026-05-21T10:00:00+00:00",
                    "created_at": "2026-05-07T10:00:00+00:00",
                    "accepted_at": None,
                    "declined_at": None,
                    "revoked_at": None,
                },
            ],
        },
    )

    oid: UUID
    product_id: UUID
    product_name: str
    recipient: UserSchema | None
    invited_email: str | None
    status: GiftStatus
    gifter: UserSchema
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_output(cls, view: ProductGiftOutput) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            product_name=view.product_name,
            recipient=(
                UserSchema.model_validate(view.recipient)
                if view.recipient is not None
                else None
            ),
            invited_email=view.invited_email,
            status=view.status,
            gifter=UserSchema.model_validate(view.gifter),
            invite_expires_at=view.invite_expires_at,
            created_at=view.created_at,
            accepted_at=view.accepted_at,
            declined_at=view.declined_at,
            revoked_at=view.revoked_at,
        )


class GiftListSchema(BaseModel):
    """List wrapper for gift projections."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"items": []}]},
    )

    items: list[GiftSchema]


# ------------------------------ routes --------------------------------- #


@product_router.get(
    "",
    summary="List gifts issued for a product",
    operation_id="listProductGifts",
    response_model=GiftListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def list_gifts(
    request: Request,
    interactor: FromDishka[ListProductGiftsQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> GiftListSchema:
    """Return gifts issued for a product (most recent first).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected list-gifts query handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.
        limit: Page size.
        offset: Page offset.

    Returns:
        :class:`GiftListSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks `manage_releases`;
            HTTP 403.
        EntityNotFoundError: Product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListProductGiftsQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return GiftListSchema(items=[GiftSchema.from_output(v) for v in views])


@product_router.post(
    "/by-user",
    summary="Gift product access to an existing user",
    operation_id="inviteGiftByUser",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedGiftSchema,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_INVITE_MAP,
)
async def invite_by_user(
    request: Request,
    payload: InviteGiftByUserSchema,
    interactor: FromDishka[InviteGiftByUserCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedGiftSchema:
    """Gift access to an already-registered user.

    The recipient gets an email with Accept / Decline buttons, an
    in-app card, and a push banner. The enrollment is created only
    when they accept.

    Args:
        request: Source of the access-token cookie.
        payload: ``user_id`` of the recipient.
        interactor: Injected gift-by-user command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``201 Created`` with the new gift's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks `manage_releases`;
            HTTP 403.
        EntityNotFoundError: Product or target user missing; HTTP 404.
        CannotGiftToOwnerError: Target equals the product author;
            HTTP 409.
        GiftAlreadyExistsError: Target already has a pending or
            accepted gift; HTTP 409.
        ProductNotGiftableError: Product type is not giftable; HTTP 409.
        CannotEnrollInUnpublishedProductError: Product is not
            published; HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        InviteGiftByUserCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            recipient_id=UserID(payload.user_id),
        ),
    )
    return CreatedGiftSchema(oid=oid)


@product_router.post(
    "/by-email",
    summary="Gift product access by email",
    operation_id="inviteGiftByEmail",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedGiftSchema,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_INVITE_MAP,
)
async def invite_by_email(
    request: Request,
    payload: InviteGiftByEmailSchema,
    interactor: FromDishka[InviteGiftByEmailCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedGiftSchema:
    """Gift access by email — the recipient may not have an account yet.

    The email's Accept / Decline buttons land the recipient on the
    SPA, which bounces through login / register and back. A per-actor
    cap of 10 email gifts per rolling 24 hours protects the email
    provider quota.

    Args:
        request: Source of the access-token cookie.
        payload: ``email`` of the recipient.
        interactor: Injected gift-by-email command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``201 Created`` with the new gift's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks `manage_releases`;
            HTTP 403.
        EntityNotFoundError: Product missing; HTTP 404.
        CannotGiftToOwnerError: Email belongs to the product author;
            HTTP 409.
        GiftAlreadyExistsError: A pending gift for this email or an
            existing gift for the matched user already exists; HTTP 409.
        ProductNotGiftableError: Product type is not giftable; HTTP 409.
        CannotEnrollInUnpublishedProductError: Product is not
            published; HTTP 409.
        EmailInviteRateLimitExceededError: Per-day email-gift cap
            reached; HTTP 429.
        EmailSendRateLimitExceededError: Caller hit the cross-flow
            per-user outbound-email cap; HTTP 429.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        InviteGiftByEmailCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            target_email=payload.email,
            actor_ip=client_ip(request),
        ),
    )
    return CreatedGiftSchema(oid=oid)


@gift_router.get(
    "/{gift_id}",
    summary="Get a gift (for the accept/decline landing page)",
    operation_id="getGift",
    response_model=GiftSchema,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_GET_MAP,
)
async def get_gift(
    request: Request,
    interactor: FromDishka[GetGiftQueryHandler],
    auth: FromDishka[Authenticator],
    gift_id: UUID = _GIFT_ID_PATH,
) -> GiftSchema:
    """Return a single gift for the email-link landing page.

    Authorised to the addressee (recipient by id or invited email)
    or the gifter only.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected get-gift query handler.
        auth: Injected authenticator.
        gift_id: Target gift, parsed from the URL path.

    Returns:
        :class:`GiftSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither the addressee nor
            the gifter; HTTP 403.
        EntityNotFoundError: Gift missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetGiftQuery(
            actor_id=ctx.user_id,
            gift_id=ProductGiftID(gift_id),
        ),
    )
    return GiftSchema.from_output(view)


@gift_router.post(
    "/{gift_id}/accept-by-token",
    summary="Accept a gift via email token",
    operation_id="acceptGiftByToken",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_ACCEPT_MAP,
)
async def accept_by_token(
    request: Request,
    payload: AcceptGiftSchema,
    interactor: FromDishka[AcceptGiftByTokenCommandHandler],
    auth: FromDishka[Authenticator],
    gift_id: UUID = _GIFT_ID_PATH,
) -> None:
    """Accept a gift using the token from the email link.

    Creates the note enrollment for the accepting user and notifies
    the gifter.

    Args:
        request: Source of the access-token cookie.
        payload: ``token`` from the gift email link.
        interactor: Injected accept-by-token command handler.
        auth: Injected authenticator.
        gift_id: Target gift, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed recipient;
            HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email gift; HTTP 403.
        EntityNotFoundError: Gift or product missing; HTTP 404.
        CannotEnrollInUnpublishedProductError: Product no longer
            published; HTTP 409.
        InviteTokenMismatchError: Token does not match; HTTP 409.
        InviteTokenExpiredError: Token TTL elapsed; HTTP 409.
        OperationNotAllowedInGiftStatusError: Gift already resolved;
            HTTP 409.
        FieldError: ``InviteToken`` invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        AcceptGiftByTokenCommand(
            actor_id=ctx.user_id,
            gift_id=ProductGiftID(gift_id),
            raw_token=payload.token,
        ),
    )


@gift_router.post(
    "/{gift_id}/accept",
    summary="Accept a gift from an in-app notification",
    operation_id="acceptGift",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_ACCEPT_MAP,
)
async def accept_in_app(
    request: Request,
    interactor: FromDishka[AcceptGiftInAppCommandHandler],
    auth: FromDishka[Authenticator],
    gift_id: UUID = _GIFT_ID_PATH,
) -> None:
    """Accept a gift from the in-app notification card (no token).

    Same as ``POST /gifts/{id}/accept-by-token`` but without the
    email token — the in-app channel is authenticated as the
    recipient.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected in-app accept command handler.
        auth: Injected authenticator.
        gift_id: Target gift, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed recipient;
            HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email gift; HTTP 403.
        EntityNotFoundError: Gift or product missing; HTTP 404.
        CannotEnrollInUnpublishedProductError: Product no longer
            published; HTTP 409.
        OperationNotAllowedInGiftStatusError: Gift already resolved;
            HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        AcceptGiftInAppCommand(
            actor_id=ctx.user_id,
            gift_id=ProductGiftID(gift_id),
        ),
    )


@gift_router.post(
    "/{gift_id}/decline",
    summary="Decline a gift",
    operation_id="declineGift",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_ACCEPT_MAP,
)
async def decline(
    request: Request,
    interactor: FromDishka[DeclineGiftCommandHandler],
    auth: FromDishka[Authenticator],
    gift_id: UUID = _GIFT_ID_PATH,
) -> None:
    """Decline a pending gift (in-app card or email link).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected decline command handler.
        auth: Injected authenticator.
        gift_id: Target gift, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed recipient;
            HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email gift; HTTP 403.
        EntityNotFoundError: Gift missing; HTTP 404.
        OperationNotAllowedInGiftStatusError: Gift already resolved;
            HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeclineGiftCommand(
            actor_id=ctx.user_id,
            gift_id=ProductGiftID(gift_id),
        ),
    )


@gift_router.delete(
    "/{gift_id}",
    summary="Revoke a pending gift",
    operation_id="revokeGift",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=GIFT_REVOKE_MAP,
)
async def revoke(
    request: Request,
    interactor: FromDishka[RevokeGiftCommandHandler],
    auth: FromDishka[Authenticator],
    gift_id: UUID = _GIFT_ID_PATH,
) -> None:
    """Cancel a still-pending gift (gifter / manager action).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected revoke command handler.
        auth: Injected authenticator.
        gift_id: Target gift, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks `manage_releases`;
            HTTP 403.
        EntityNotFoundError: Gift missing; HTTP 404.
        OperationNotAllowedInGiftStatusError: Gift is not pending
            (already accepted/declined/revoked); HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RevokeGiftCommand(
            actor_id=ctx.user_id,
            gift_id=ProductGiftID(gift_id),
        ),
    )
