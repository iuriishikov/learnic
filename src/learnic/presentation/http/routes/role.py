"""Roles HTTP routes — per-product role catalogue.

Roles are bundles of :class:`Permission` values (from the role
aggregate). Each role belongs to exactly one product and is managed
by collaborators with ``MANAGE_ROLES`` (the product author has every
permission by short-circuit). The Team-tab onboarding flow on the
SPA bootstraps an initial role set on first open when the product's
role list is empty.
"""

from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.role.create import (
    CreateCustomRoleCommand,
    CreateCustomRoleCommandHandler,
)
from learnic.application.commands.role.delete import (
    DeleteCustomRoleCommand,
    DeleteCustomRoleCommandHandler,
)
from learnic.application.commands.role.update import (
    UpdateCustomRoleCommand,
    UpdateCustomRoleCommandHandler,
)
from learnic.application.common.persistence.role import RoleView
from learnic.application.queries.role.get import (
    GetRoleQuery,
    GetRoleQueryHandler,
)
from learnic.application.queries.role.list import (
    ListProductRolesQuery,
    ListProductRolesQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.constants import (
    ROLE_DESCRIPTION_MAX_LEN,
    ROLE_NAME_MAX_LEN,
    ROLE_NAME_MIN_LEN,
)
from learnic.entities.common.limits import ResourceLimitReachedError
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    RESOURCE_LIMIT_RULE,
    ROLE_DELETE_MAP,
    ROLE_MUTATION_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/products/{product_id}/roles",
    tags=["Roles"],
    route_class=DishkaErrorAwareRoute,
)

role_router = ErrorAwareRouter(
    prefix="/roles",
    tags=["Roles"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_PRODUCT_ID_PATH: Final = Path(
    description="Owning product UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_ROLE_ID_PATH: Final = Path(
    description="Target role UUID.",
    examples=["e7c2a8f0-1b34-4d6e-9c89-08d7641a2b15"],
)


# --------------------------- request schemas --------------------------- #


class CreateRoleSchema(BaseModel):
    """Body for ``POST /products/{product_id}/roles``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Lead Editor",
                    "description": "Full editing power except publish.",
                    "permissions": [
                        "read_product",
                        "edit_modules",
                        "edit_lessons",
                        "edit_description",
                    ],
                },
            ],
        },
    )

    name: str = Field(
        description=(
            "Role name, unique within the product. "
            f"Length is `{ROLE_NAME_MIN_LEN}..{ROLE_NAME_MAX_LEN}` "
            "(`ROLE_NAME_MAX_LEN`)."
        ),
        min_length=ROLE_NAME_MIN_LEN,
        max_length=ROLE_NAME_MAX_LEN,
        examples=["Lead Editor"],
    )
    description: str | None = Field(
        default=None,
        description=(
            "Optional human-readable description shown alongside "
            f"the role. Max length `{ROLE_DESCRIPTION_MAX_LEN}`."
        ),
        max_length=ROLE_DESCRIPTION_MAX_LEN,
        examples=["Full editing power except publish."],
    )
    permissions: list[Permission] = Field(
        description=(
            "Permission set granted by this role. Must contain at "
            "least one entry. Implications are added automatically "
            "by the authoriser at check time (e.g. `edit_modules` "
            "implies `edit_lessons`)."
        ),
        min_length=1,
        examples=[
            [
                "read_product",
                "edit_modules",
                "edit_lessons",
                "edit_description",
            ],
        ],
    )


class UpdateRoleSchema(BaseModel):
    """Body for ``PATCH /roles/{role_id}``.

    All fields are optional. ``description`` uses two fields together
    to distinguish "leave as-is" (`null`) from "explicitly clear"
    (`clear_description=true`).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Module Owner",
                    "permissions": ["read_product", "edit_modules"],
                },
                {
                    "description": None,
                    "clear_description": True,
                },
            ],
        },
    )

    name: str | None = Field(
        default=None,
        description=(
            "New role name. `null` means leave unchanged. Length "
            f"`{ROLE_NAME_MIN_LEN}..{ROLE_NAME_MAX_LEN}`."
        ),
        min_length=ROLE_NAME_MIN_LEN,
        max_length=ROLE_NAME_MAX_LEN,
        examples=["Module Owner"],
    )
    description: str | None = Field(
        default=None,
        description=(
            "New description. `null` plus "
            "`clear_description=true` clears it explicitly; `null` "
            "alone leaves the existing value untouched. Max length "
            f"`{ROLE_DESCRIPTION_MAX_LEN}`."
        ),
        max_length=ROLE_DESCRIPTION_MAX_LEN,
        examples=["Owns module structure."],
    )
    clear_description: bool = Field(
        default=False,
        description=(
            "Set to `true` together with `description=null` to "
            "explicitly clear the description."
        ),
        examples=[False],
    )
    permissions: list[Permission] | None = Field(
        default=None,
        description=(
            "Replacement permission set. `null` means leave "
            "unchanged. Must contain at least one entry when set."
        ),
        min_length=1,
        examples=[["read_product", "edit_modules"]],
    )


# --------------------------- response schemas -------------------------- #


class RoleSchema(BaseModel):
    """Role response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "e7c2a8f0-1b34-4d6e-9c89-08d7641a2b15",
                    "product_id": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "name": "Lead Editor",
                    "description": "Full editing power except publish.",
                    "position": 1010,
                    "permissions": [
                        "read_product",
                        "edit_description",
                        "edit_lessons",
                        "edit_modules",
                    ],
                    "created_by": ("550e8400-e29b-41d4-a716-446655440000"),
                    "created_at": "2026-05-07T10:00:00+00:00",
                    "updated_at": "2026-05-07T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID
    product_id: UUID
    name: str
    description: str | None
    position: int = Field(
        description=(
            "Discord-style hierarchy slot. Lower number = higher rank. "
            "The product owner has synthetic position `0` (never stored). "
            "A caller with `manage_collaborators` may only assign roles "
            "with `position` strictly greater than their own highest "
            "role's position; the API enforces this and returns 403 "
            "`RoleHierarchyViolation` when the rule is broken."
        ),
        examples=[10, 20, 1010],
    )
    permissions: list[Permission]
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: RoleView) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            name=view.name,
            description=view.description,
            position=view.position,
            permissions=sorted(view.permissions, key=str),
            created_by=view.created_by,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


class RoleListSchema(BaseModel):
    """List wrapper for role catalogues."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"items": []}]})

    items: list[RoleSchema]


class CreatedRoleSchema(BaseModel):
    """Response body for ``POST /products/{product_id}/roles``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"oid": "e7c2a8f0-1b34-4d6e-9c89-08d7641a2b15"}],
        },
    )

    oid: UUID


# ------------------------------ routes --------------------------------- #


@router.get(
    "",
    summary="List roles available inside a product",
    operation_id="listProductRoles",
    response_model=RoleListSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def list_product_roles(
    request: Request,
    interactor: FromDishka[ListProductRolesQueryHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> RoleListSchema:
    """Return the roles defined inside a product.

    Returns an empty list when the product has no roles yet — the
    SPA's Team-tab onboarding flow uses that signal to prompt the
    author to create an initial set.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected list-roles query handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        :class:`RoleListSchema` with the product's roles ordered by
        ``position`` ascending (highest-rank first).

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Product missing; HTTP 404.
        InsufficientPermissionsError: Caller lacks `read_product`;
            HTTP 403.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        ListProductRolesQuery(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
        ),
    )
    return RoleListSchema(items=[RoleSchema.from_view(v) for v in views])


@router.post(
    "",
    summary="Create a custom role inside a product",
    operation_id="createCustomRole",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedRoleSchema,
    dependencies=_AUTH_SECURITY,
    error_map=ROLE_MUTATION_MAP
    | {ResourceLimitReachedError: RESOURCE_LIMIT_RULE},
)
async def create_custom_role(
    request: Request,
    payload: CreateRoleSchema,
    interactor: FromDishka[CreateCustomRoleCommandHandler],
    auth: FromDishka[Authenticator],
    product_id: UUID = _PRODUCT_ID_PATH,
) -> CreatedRoleSchema:
    """Create a custom role inside a product.

    Args:
        request: Source of the access-token cookie.
        payload: Role definition (name, optional description,
            non-empty permission set).
        interactor: Injected create-role command handler.
        auth: Injected authenticator.
        product_id: Owning product, parsed from the URL path.

    Returns:
        ``201 Created`` with the new role's `oid`.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Product missing; HTTP 404.
        InsufficientPermissionsError: Caller lacks `manage_roles`;
            HTTP 403.
        RoleNameAlreadyTakenError: Name already used inside this
            product; HTTP 409.
        ResourceLimitReachedError: The product already has
            ``ROLE_LIMIT`` roles; HTTP 409.
        FieldError: ``RoleName`` / ``RoleDescription`` /
            ``PermissionSet`` invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    role_id = await interactor.run(
        CreateCustomRoleCommand(
            actor_id=ctx.user_id,
            product_id=ProductID(product_id),
            name=payload.name,
            description=payload.description,
            permissions=frozenset(payload.permissions),
        ),
    )
    return CreatedRoleSchema(oid=role_id)


@role_router.get(
    "/{role_id}",
    summary="Get a single role",
    operation_id="getRoleById",
    response_model=RoleSchema,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def get_role(
    request: Request,
    interactor: FromDishka[GetRoleQueryHandler],
    auth: FromDishka[Authenticator],
    role_id: UUID = _ROLE_ID_PATH,
) -> RoleSchema:
    """Return a role by id (system or custom).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected get-role query handler.
        auth: Injected authenticator.
        role_id: Target role's UUID, parsed from the URL path.

    Returns:
        :class:`RoleSchema` with the role's metadata and permissions.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: No role with the given id; HTTP 404.
        InsufficientPermissionsError: Caller is not a collaborator on
            the role's product; HTTP 403.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetRoleQuery(actor_id=ctx.user_id, role_id=RoleID(role_id)),
    )
    return RoleSchema.from_view(view)


@role_router.patch(
    "/{role_id}",
    summary="Update a custom role",
    operation_id="updateCustomRole",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ROLE_MUTATION_MAP,
)
async def update_custom_role(
    request: Request,
    payload: UpdateRoleSchema,
    interactor: FromDishka[UpdateCustomRoleCommandHandler],
    auth: FromDishka[Authenticator],
    role_id: UUID = _ROLE_ID_PATH,
) -> None:
    """Update a custom role.

    Args:
        request: Source of the access-token cookie.
        payload: Optional-field update — ``null`` means "leave as-is".
        interactor: Injected update-role command handler.
        auth: Injected authenticator.
        role_id: Target role's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Role missing; HTTP 404.
        InsufficientPermissionsError: Caller lacks `manage_roles`;
            HTTP 403.
        RoleNameAlreadyTakenError: New name conflicts; HTTP 409.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCustomRoleCommand(
            actor_id=ctx.user_id,
            role_id=RoleID(role_id),
            name=payload.name,
            description=payload.description,
            clear_description=payload.clear_description,
            permissions=(
                frozenset(payload.permissions)
                if payload.permissions is not None
                else None
            ),
        ),
    )


@role_router.delete(
    "/{role_id}",
    summary="Delete a custom role",
    operation_id="deleteCustomRole",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ROLE_DELETE_MAP,
)
async def delete_custom_role(
    request: Request,
    interactor: FromDishka[DeleteCustomRoleCommandHandler],
    auth: FromDishka[Authenticator],
    role_id: UUID = _ROLE_ID_PATH,
) -> None:
    """Delete a custom role.

    Returns ``409 RoleInUse`` if the role is still referenced by any
    collaboration grant; the API client must reassign affected
    collaborators (or revoke them) before retrying.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected delete-role command handler.
        auth: Injected authenticator.
        role_id: Target role's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: Role missing; HTTP 404.
        InsufficientPermissionsError: Caller lacks `manage_roles`;
            HTTP 403.
        RoleInUseError: Role still assigned; HTTP 409.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteCustomRoleCommand(
            actor_id=ctx.user_id,
            role_id=RoleID(role_id),
        ),
    )
