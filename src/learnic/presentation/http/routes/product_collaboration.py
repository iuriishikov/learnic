"""Collaboration HTTP routes — invites, grants, and self-service.

Two router objects are exported:

- :data:`product_router` is mounted under
  ``/products/{product_id}/collaborations`` and carries the
  product-scoped operations (invite, list).
- :data:`collab_router` is mounted under ``/collaborations`` and
  carries the operations addressed by collaboration id (accept,
  update grants, revoke).
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Query, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
)
from learnic.application.common.formatting import mask_email
from learnic.application.commands.product_collaboration.accept import (
    AcceptCollaborationInviteCommand,
    AcceptCollaborationInviteCommandHandler,
)
from learnic.application.commands.product_collaboration.accept_in_app import (
    AcceptCollaborationInAppCommand,
    AcceptCollaborationInAppCommandHandler,
)
from learnic.application.commands.product_collaboration.decline_in_app import (
    DeclineCollaborationInAppCommand,
    DeclineCollaborationInAppCommandHandler,
)
from learnic.application.commands.product_collaboration.invite_by_email import (
    InviteCollaboratorByEmailCommand,
    InviteCollaboratorByEmailCommandHandler,
)
from learnic.application.commands.product_collaboration.invite_by_user import (
    InviteCollaboratorByUserCommand,
    InviteCollaboratorByUserCommandHandler,
)
from learnic.application.commands.product_collaboration.leave import (
    LeaveProductCommand,
    LeaveProductCommandHandler,
)
from learnic.application.commands.product_collaboration.reinvite import (
    ReinviteCollaboratorCommand,
    ReinviteCollaboratorCommandHandler,
)
from learnic.application.commands.product_collaboration.revoke import (
    RevokeCollaborationCommand,
    RevokeCollaborationCommandHandler,
)
from learnic.application.commands.product_collaboration.update_grants import (
    UpdateCollaborationGrantsCommand,
    UpdateCollaborationGrantsCommandHandler,
)
from learnic.application.common.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Pagination,
)
from learnic.application.common.persistence.product_collaboration import (
    CollaborationGrantView,
    ProductCollaborationView,
)
from learnic.application.queries.product_collaboration.get_my_permissions import (
    EffectivePermissionsView,
    GetMyEffectivePermissionsQuery,
    GetMyEffectivePermissionsQueryHandler,
)
from learnic.application.queries.product_collaboration.list_for_product import (
    ListProductCollaboratorsQuery,
    ListProductCollaboratorsQueryHandler,
)
from learnic.application.queries.product_collaboration.list_my import (
    ListMyCollaborationsQuery,
    ListMyCollaborationsQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import (
    CollaborationStatus,
)
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission, ScopeType
from learnic.entities.user.constants import EMAIL_MAX_LEN
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    COLLABORATION_ACCEPT_MAP,
    COLLABORATION_INVITE_MAP,
    COLLABORATION_MUTATION_MAP,
)
from learnic.presentation.http.common.device import client_ip
from learnic.presentation.http.common.router import DishkaErrorAwareRoute
from learnic.presentation.http.common.schemas import UserRefSchema

product_router = ErrorAwareRouter(
    prefix="/products/{product_id}/collaborations",
    tags=["Collaborations"],
    route_class=DishkaErrorAwareRoute,
)

collab_router = ErrorAwareRouter(
    prefix="/collaborations",
    tags=["Collaborations"],
    route_class=DishkaErrorAwareRoute,
)

me_router = ErrorAwareRouter(
    prefix="/collaborations",
    tags=["Collaborations"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Owning product UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_COLLAB_ID_PATH: Final = Path(
    description="Target collaboration UUID.",
    examples=["a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001"],
)


# --------------------------- request schemas --------------------------- #


class GrantSpecSchema(BaseModel):
    """Single ``(role, scope)`` pair inside an invite or update body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "role_id": "00000000-0000-0000-0000-000000000003",
                    "scope_type": "product",
                    "scope_id": None,
                },
                {
                    "role_id": "e7c2a8f0-1b34-4d6e-9c89-08d7641a2b15",
                    "scope_type": "module",
                    "scope_id": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8",
                },
            ],
        },
    )

    role_id: UUID = Field(
        description=("System or product-custom role to grant under this scope."),
        examples=["00000000-0000-0000-0000-000000000003"],
    )
    scope_type: ScopeType = Field(
        description=(
            "Granularity at which the role applies. `product` covers "
            "everything; `module` covers a single module + its "
            "lessons; `lesson` covers only one lesson."
        ),
        examples=["product"],
    )
    scope_id: UUID | None = Field(
        default=None,
        description=(
            "Required for `module` / `lesson` scopes; must be `null` "
            "for `product` scope. Validated against the target "
            "product so cross-product ids are rejected."
        ),
        examples=[None, "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
    )

    def to_spec(self) -> GrantSpec:
        return GrantSpec(
            role_id=RoleID(self.role_id),
            scope_type=self.scope_type,
            scope_id=self.scope_id,
        )


class InviteByUserSchema(BaseModel):
    """Body for ``POST /products/{product_id}/collaborations/by-user``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "grants": [
                        {
                            "role_id": ("00000000-0000-0000-0000-000000000003"),
                            "scope_type": "product",
                            "scope_id": None,
                        },
                    ],
                },
            ],
        },
    )

    user_id: UUID = Field(
        description="Target user — must already have a registered account.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    grants: list[GrantSpecSchema] = Field(
        description=(
            "Role + scope assignments granted to the invitee on "
            "accept. Must contain at least one entry."
        ),
        min_length=1,
    )


class InviteByEmailSchema(BaseModel):
    """Body for ``POST /products/{product_id}/collaborations/by-email``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "invited@example.com",
                    "grants": [
                        {
                            "role_id": ("00000000-0000-0000-0000-000000000002"),
                            "scope_type": "product",
                            "scope_id": None,
                        },
                    ],
                },
            ],
        },
    )

    email: str = Field(
        description=(
            "Target email — does not need to be a registered user "
            "yet. Validated by the domain `Email` value object on "
            f"the server side. Max length `{EMAIL_MAX_LEN}` "
            "(`EMAIL_MAX_LEN`)."
        ),
        min_length=3,
        max_length=EMAIL_MAX_LEN,
        examples=["invited@example.com"],
    )
    grants: list[GrantSpecSchema] = Field(
        description=(
            "Role + scope assignments granted on accept. Must "
            "contain at least one entry."
        ),
        min_length=1,
    )


class AcceptInviteSchema(BaseModel):
    """Body for ``POST /collaborations/{collaboration_id}/accept-by-token``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"token": "01HJ7K8...some-opaque-token"},
            ],
        },
    )

    token: str = Field(
        description=(
            "Plaintext token from the invite email link. The server "
            "compares its sha256 against the stored hash."
        ),
        min_length=1,
        examples=["01HJ7K8...some-opaque-token"],
    )


class UpdateGrantsSchema(BaseModel):
    """Body for ``PUT /collaborations/{collaboration_id}/grants``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grants": [
                        {
                            "role_id": ("00000000-0000-0000-0000-000000000004"),
                            "scope_type": "product",
                            "scope_id": None,
                        },
                    ],
                },
            ],
        },
    )

    grants: list[GrantSpecSchema] = Field(
        description=("Replacement grant set. Must contain at least one entry."),
        min_length=1,
    )


# --------------------------- response schemas -------------------------- #


class GrantSchema(BaseModel):
    """Grant projection inside a collaboration response."""

    oid: UUID
    role_id: UUID
    role_name: str
    scope_type: ScopeType
    scope_id: UUID | None

    @classmethod
    def from_view(cls, view: CollaborationGrantView) -> Self:
        return cls(
            oid=view.oid,
            role_id=view.role_id,
            role_name=view.role_name,
            scope_type=view.scope_type,
            scope_id=view.scope_id,
        )


class CollaborationSchema(BaseModel):
    """Collaboration response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001",
                    "product_id": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "collaborator": {
                        "oid": ("550e8400-e29b-41d4-a716-446655440000"),
                        "full_name": "Lovelace Ada",
                        "email": "a*****a@example.com",
                    },
                    "invited_email": None,
                    "status": "active",
                    "invited_by": ("8b1c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "invite_expires_at": None,
                    "created_at": "2026-05-07T10:00:00+00:00",
                    "accepted_at": "2026-05-07T11:00:00+00:00",
                    "declined_at": None,
                    "revoked_at": None,
                    "grants": [
                        {
                            "oid": ("f1e2d3c4-5566-7788-99aa-bbccddeeff00"),
                            "role_id": ("00000000-0000-0000-0000-000000000003"),
                            "role_name": "Editor",
                            "scope_type": "product",
                            "scope_id": None,
                        },
                    ],
                },
            ],
        },
    )

    oid: UUID
    product_id: UUID
    collaborator: UserRefSchema | None
    invited_email: str | None
    status: CollaborationStatus
    invited_by: UUID
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    grants: list[GrantSchema]

    @classmethod
    def from_view(cls, view: ProductCollaborationView) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            collaborator=(
                UserRefSchema.from_view(view.collaborator)
                if view.collaborator is not None
                else None
            ),
            invited_email=(
                mask_email(view.invited_email)
                if view.invited_email is not None
                else None
            ),
            status=view.status,
            invited_by=view.invited_by,
            invite_expires_at=view.invite_expires_at,
            created_at=view.created_at,
            accepted_at=view.accepted_at,
            declined_at=view.declined_at,
            revoked_at=view.revoked_at,
            grants=[GrantSchema.from_view(g) for g in view.grants],
        )


class CollaborationListSchema(BaseModel):
    """List wrapper for collaboration projections."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"items": []}]},
    )

    items: list[CollaborationSchema]


class CreatedCollaborationSchema(BaseModel):
    """Response body for collaboration invite endpoints."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "a4f1c08d-2e5b-4ad7-b2e6-5d28a1f6c001"},
            ],
        },
    )

    oid: UUID


class EffectivePermissionsSchema(BaseModel):
    """Resolved permissions of the calling user on a product."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "permissions": ["read_product", "edit_modules"],
                    "hierarchy_position": 200,
                },
                {"permissions": [], "hierarchy_position": None},
                {
                    "permissions": [
                        "read_product",
                        "manage_collaborators",
                        "manage_roles",
                        "publish",
                        "archive",
                    ],
                    "hierarchy_position": 0,
                },
            ],
        },
    )

    permissions: list[Permission]
    hierarchy_position: int | None = Field(
        description=(
            "Discord-style rank of the caller on this product. "
            "`0` for the product owner, a positive integer for a "
            "collaborator (lowest = highest-rank role), or `null` "
            "when the caller has no rank at all. Frontends use it "
            "to filter assignable roles and hide management actions "
            "on members at or above the caller."
        ),
        examples=[None, 0, 100, 200, 1010],
    )

    @classmethod
    def from_view(cls, view: EffectivePermissionsView) -> Self:
        return cls(
            permissions=list(view.permissions),
            hierarchy_position=view.hierarchy_position,
        )


# ------------------------------ routes --------------------------------- #


@product_router.get(
    "",
    summary="List collaborators on a product",
    operation_id="listProductCollaborators",
    response_model=CollaborationListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def list_collaborators(
    request: Request,
    interactor: FromDishka[ListProductCollaboratorsQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> CollaborationListSchema:
    """Return active and pending collaborators for a product.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected list-collaborators query handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.
        limit: Page size (`1..MAX_LIMIT`).
        offset: Page offset.

    Returns:
        :class:`CollaborationListSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `read_product` (i.e. is not a collaborator); HTTP 403.
        EntityNotFoundError: Product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListProductCollaboratorsQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return CollaborationListSchema(
        items=[CollaborationSchema.from_view(v) for v in views],
    )


@product_router.post(
    "/by-user",
    summary="Invite an existing user as a collaborator",
    operation_id="inviteCollaboratorByUser",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedCollaborationSchema,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_INVITE_MAP,
)
async def invite_by_user(
    request: Request,
    payload: InviteByUserSchema,
    interactor: FromDishka[InviteCollaboratorByUserCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedCollaborationSchema:
    """Invite an already-registered user.

    The target receives an email with a link of the shape
    ``{frontend}/products/{product_id}/collaboration-invitation/
    {collaboration_id}/accept?token=...``. They must accept via that
    link before any grants take effect.

    Args:
        request: Source of the access-token cookie.
        payload: ``user_id`` + at least one grant.
        interactor: Injected invite-by-user command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``201 Created`` with the new collaboration's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `manage_collaborators`; HTTP 403.
        EntityNotFoundError: Product or target user missing, or a
            scope id outside the product; HTTP 404.
        CannotInviteOwnerError: Target equals the product author;
            HTTP 409.
        CollaborationAlreadyExistsError: Target already has an active
            or pending collaboration; HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        InviteCollaboratorByUserCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            target_user_id=UserID(payload.user_id),
            grants=[g.to_spec() for g in payload.grants],
        ),
    )
    return CreatedCollaborationSchema(oid=oid)


@product_router.post(
    "/by-email",
    summary="Invite a (possibly unregistered) user by email",
    operation_id="inviteCollaboratorByEmail",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedCollaborationSchema,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_INVITE_MAP,
)
async def invite_by_email(
    request: Request,
    payload: InviteByEmailSchema,
    interactor: FromDishka[InviteCollaboratorByEmailCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedCollaborationSchema:
    """Invite by email — invitee may not have an account yet.

    See :func:`invite_by_user` for the link shape and accept flow.

    The handler enforces a per-actor cap of 10 email invitations
    per rolling 24 hours so a single account cannot drain the
    upstream email-provider quota with a flood of invites to
    attacker-controlled addresses.

    Args:
        request: Source of the access-token cookie.
        payload: ``email`` + at least one grant.
        interactor: Injected invite-by-email command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``201 Created`` with the new collaboration's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `manage_collaborators`; HTTP 403.
        EntityNotFoundError: Product missing or scope id outside the
            product; HTTP 404.
        CannotInviteOwnerError: Email belongs to the product author;
            HTTP 409.
        CollaborationAlreadyExistsError: A pending invite for this
            email or an active collaboration for the matched user
            already exists; HTTP 409.
        EmailInviteRateLimitExceededError: Caller has already issued
            the per-day limit of email invitations; HTTP 429.
        EmailSendRateLimitExceededError: Caller hit the cross-flow
            per-user outbound-email cap; HTTP 429.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        InviteCollaboratorByEmailCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            target_email=payload.email,
            grants=[g.to_spec() for g in payload.grants],
            actor_ip=client_ip(request),
        ),
    )
    return CreatedCollaborationSchema(oid=oid)


@product_router.delete(
    "/me",
    summary="Leave a product as a collaborator (self-revoke)",
    operation_id="leaveProduct",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def leave_product(
    request: Request,
    interactor: FromDishka[LeaveProductCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Self-revoke from a collaboration.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected leave-product command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Product missing or caller is not an
            active collaborator; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        LeaveProductCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )


@collab_router.post(
    "/{collaboration_id}/accept-by-token",
    summary="Accept a pending collaboration invite via email token",
    operation_id="acceptCollaborationInviteByToken",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_ACCEPT_MAP,
)
async def accept_invite(
    request: Request,
    payload: AcceptInviteSchema,
    interactor: FromDishka[AcceptCollaborationInviteCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> None:
    """Accept a collaboration invite.

    For by-user invites the caller's id must equal
    ``collaboration.collaborator_id``; for by-email invites the
    caller's account email must equal ``invited_email``.

    Args:
        request: Source of the access-token cookie.
        payload: ``token`` from the invite email.
        interactor: Injected accept-invite command handler.
        auth: Injected authenticator.
        collaboration_id: Target collaboration, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed by-user
            invitee; HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email invite; HTTP 403.
        EntityNotFoundError: Collaboration missing; HTTP 404.
        FieldError: ``InviteToken`` invariants violated, or token
            mismatch / expiration surfaced as a domain error; HTTP
            422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        AcceptCollaborationInviteCommand(
            actor_id=ctx.user_id,
            collaboration_id=ProductCollaborationID(collaboration_id),
            raw_token=payload.token,
        ),
    )


@collab_router.post(
    "/{collaboration_id}/accept",
    summary="Accept a pending collaboration invite",
    operation_id="acceptCollaborationInvite",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_ACCEPT_MAP,
)
async def accept_invite_in_app(
    request: Request,
    interactor: FromDishka[AcceptCollaborationInAppCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> None:
    """Accept a collaboration invite from an in-app notification.

    Same as ``POST /collaborations/{id}/accept-by-token`` but
    without the email-link token. The in-app channel is itself authenticated as
    the recipient, so identity-based authorisation is sufficient.

    For by-user invites the caller's id must equal
    ``collaboration.collaborator_id``; for by-email invites the
    caller's account email must equal ``invited_email``.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected in-app accept command handler.
        auth: Injected authenticator.
        collaboration_id: Target collaboration, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed by-user
            invitee; HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email invite; HTTP 403.
        EntityNotFoundError: Collaboration missing; HTTP 404.
        FieldError: Domain invariants violated (e.g. expired or
            non-pending status); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        AcceptCollaborationInAppCommand(
            actor_id=ctx.user_id,
            collaboration_id=ProductCollaborationID(collaboration_id),
        ),
    )


@collab_router.post(
    "/{collaboration_id}/decline",
    summary="Decline a pending collaboration invite",
    operation_id="declineCollaborationInvite",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_ACCEPT_MAP,
)
async def decline_invite_in_app(
    request: Request,
    interactor: FromDishka[DeclineCollaborationInAppCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> None:
    """Decline a collaboration invite from an in-app notification.

    Mirror of ``POST /collaborations/{id}/accept`` — same
    identity-based authorisation, but flips the collaboration to
    :class:`CollaborationStatus.DECLINED` and broadcasts a
    ``COLLABORATION_DECLINED`` product event so the inviter's
    collaborators screen reacts in real time. The recipient's
    surviving ``invite_sent`` notification is republished on the
    notifications WS channel with the updated collaboration
    snapshot so the panel re-renders the row as resolved.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected in-app decline command handler.
        auth: Injected authenticator.
        collaboration_id: Target collaboration, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is not the addressed by-user
            invitee; HTTP 403.
        InviteEmailMismatchError: Caller's email does not match the
            by-email invite; HTTP 403.
        EntityNotFoundError: Collaboration missing; HTTP 404.
        FieldError: Domain invariants violated (e.g. non-pending
            status); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeclineCollaborationInAppCommand(
            actor_id=ctx.user_id,
            collaboration_id=ProductCollaborationID(collaboration_id),
        ),
    )


@collab_router.put(
    "/{collaboration_id}/grants",
    summary="Replace grants of a collaboration",
    operation_id="updateCollaborationGrants",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_MUTATION_MAP,
)
async def update_grants(
    request: Request,
    payload: UpdateGrantsSchema,
    interactor: FromDishka[UpdateCollaborationGrantsCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> None:
    """Atomically replace a collaboration's grant set.

    Args:
        request: Source of the access-token cookie.
        payload: Replacement grant list (non-empty).
        interactor: Injected update-grants command handler.
        auth: Injected authenticator.
        collaboration_id: Target collaboration, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `manage_collaborators`; HTTP 403.
        EntityNotFoundError: Collaboration or referenced role/scope
            missing; HTTP 404.
        FieldError: VO invariants violated, or attempting to mutate a
            non-active collaboration; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCollaborationGrantsCommand(
            actor_id=ctx.user_id,
            collaboration_id=ProductCollaborationID(collaboration_id),
            grants=[g.to_spec() for g in payload.grants],
        ),
    )


@collab_router.delete(
    "/{collaboration_id}",
    summary="Revoke a collaboration",
    operation_id="revokeCollaboration",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_MUTATION_MAP,
)
async def revoke(
    request: Request,
    interactor: FromDishka[RevokeCollaborationCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> None:
    """Revoke an active or pending collaboration.

    The collaborator (if known) is notified by email.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected revoke-collaboration command handler.
        auth: Injected authenticator.
        collaboration_id: Target collaboration, parsed from the URL
            path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `manage_collaborators`; HTTP 403.
        EntityNotFoundError: Collaboration missing; HTTP 404.
        OperationNotAllowedInStatusError: Collaboration is in a status
            where ``revoke`` is forbidden (already terminal); HTTP 409
            via ``OPERATION_NOT_ALLOWED_IN_STATUS_RULE``.
        EmailSendRateLimitExceededError: Caller hit the cross-flow
            per-user outbound-email cap (the revoked collaborator is
            notified by email); HTTP 429.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RevokeCollaborationCommand(
            actor_id=ctx.user_id,
            collaboration_id=ProductCollaborationID(collaboration_id),
            actor_ip=client_ip(request),
        ),
    )


@collab_router.post(
    "/{collaboration_id}/reinvite",
    summary="Re-invite a collaborator after a previous declined/revoked invite",
    operation_id="reinviteCollaborator",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedCollaborationSchema,
    dependencies=_AUTH_SECURITY,
    error_map=COLLABORATION_INVITE_MAP,
)
async def reinvite(
    request: Request,
    interactor: FromDishka[ReinviteCollaboratorCommandHandler],
    auth: FromDishka[Authenticator],
    collaboration_id: UUID = _COLLAB_ID_PATH,
) -> CreatedCollaborationSchema:
    """Re-invite a collaborator from a terminal collaboration row.

    Reads the source collaboration to recover the original target
    (registered user id or email) and grants, then creates a new
    pending invitation with the same scope. The previous row stays
    in its terminal state for audit; this operation never resurrects
    it. The new collaboration's id is returned in the response body.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected re-invite command handler.
        auth: Injected authenticator.
        collaboration_id: Source (declined/revoked) collaboration,
            parsed from the URL path.

    Returns:
        ``201 Created`` with the new collaboration's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        InsufficientPermissionsError: Caller lacks
            `manage_collaborators`; HTTP 403.
        EntityNotFoundError: Source collaboration missing or its
            target cannot be resolved; HTTP 404.
        CollaborationAlreadyExistsError: A new active or pending
            invite already exists for the same target; HTTP 409.
        EmailInviteRateLimitExceededError: Email rate cap reached;
            HTTP 429.
        EmailSendRateLimitExceededError: Caller hit the cross-flow
            per-user outbound-email cap; HTTP 429.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    oid = await interactor.run(
        ReinviteCollaboratorCommand(
            actor_id=ctx.user_id,
            source_collaboration_id=ProductCollaborationID(collaboration_id),
            actor_ip=client_ip(request),
        ),
    )
    return CreatedCollaborationSchema(oid=oid)


@me_router.get(
    "/mine",
    summary="List collaborations of the current user",
    operation_id="listMyCollaborations",
    response_model=CollaborationListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def list_mine(
    request: Request,
    interactor: FromDishka[ListMyCollaborationsQueryHandler],
    auth: FromDishka[Authenticator],
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> CollaborationListSchema:
    """List the caller's collaborations across products.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected list-my-collaborations query handler.
        auth: Injected authenticator.
        limit: Page size (`1..MAX_LIMIT`).
        offset: Page offset.

    Returns:
        :class:`CollaborationListSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListMyCollaborationsQuery(
            actor_id=ctx.user_id,
            pagination=Pagination(limit=limit, offset=offset),
        ),
    )
    return CollaborationListSchema(
        items=[CollaborationSchema.from_view(v) for v in views],
    )


@product_router.get(
    "/me/permissions",
    summary="Effective permissions of the current user on a product",
    operation_id="getMyEffectivePermissions",
    response_model=EffectivePermissionsSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def my_effective_permissions(
    request: Request,
    interactor: FromDishka[GetMyEffectivePermissionsQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> EffectivePermissionsSchema:
    """Resolve the caller's effective permissions on a product.

    Returns an empty list when the caller has no access — the route
    itself does not raise 403; the SPA uses the empty list to render
    a "no access" or "request access" UI.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected get-my-permissions query handler.
        auth: Injected authenticator.
        product_id: Target product, parsed from the URL path.

    Returns:
        :class:`EffectivePermissionsSchema`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetMyEffectivePermissionsQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    return EffectivePermissionsSchema.from_view(view)
