"""HTTP routes for billing — subscription read, plus admin grants.

Three routers ship here:

* ``router`` — ``/users/me/subscription`` for the caller-scoped read
  (CLAUDE.md rule 14: "everything about the authenticated user" is
  namespaced under ``/users/me/...``).
* ``admin_router`` — ``/admin/users/{user_id}/subscription`` for the
  admin grant / revoke pair: an administrator gives a user free
  access to a tariff (BETA by default) or drops them back to FREE.
  Admin-only via ``AdminAuthenticator``; kept under the ``Billing``
  tag (not ``Admin``) so all subscription operations are discoverable
  together in Swagger.
* ``note_router`` — ``/notes/{note_id}/storage-remaining`` and
  ``/notes/{note_id}/storage`` nest under the parent note (rule
  14: sub-resources mirror the aggregate tree). Both report the
  *note author's* pool so a collaborator opening an editor sees
  the same numbers the author would; ``/storage`` additionally
  carries the note's own share of the pool for the editor's
  storage card. The matching live channel is
  ``WS /notes/{note_id}/storage`` (see ``## WebSocket channels``).
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from typing_extensions import Self

from learnic.application.commands.billing.grant_subscription import (
    GrantedSubscription,
    GrantSubscriptionCommand,
    GrantSubscriptionCommandHandler,
)
from learnic.application.commands.billing.revoke_subscription import (
    RevokeSubscriptionCommand,
    RevokeSubscriptionCommandHandler,
)
from learnic.application.queries.billing.get_note_storage import (
    GetNoteStorageQuery,
    GetNoteStorageQueryHandler,
    NoteStorageView,
)
from learnic.application.queries.billing.get_note_storage_remaining import (
    NoteStorageRemainingView,
    GetNoteStorageRemainingQuery,
    GetNoteStorageRemainingQueryHandler,
)
from learnic.application.queries.billing.get_my_subscription import (
    GetMySubscriptionQuery,
    GetMySubscriptionQueryHandler,
)
from learnic.entities.billing.constants import PLAN_CODE_MAX_LEN
from learnic.entities.billing.ids import PlanCode
from learnic.entities.billing.plan import BETA
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.admin_deps import AdminAuthenticator
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    ADMIN_MAP,
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    AUTHENTICATED_MAP,
    SUBSCRIPTION_GRANT_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/users/me/subscription",
    tags=["Billing"],
    route_class=DishkaErrorAwareRoute,
)

admin_router = ErrorAwareRouter(
    prefix="/admin/users",
    tags=["Billing"],
    route_class=DishkaErrorAwareRoute,
)

note_router = ErrorAwareRouter(
    prefix="/notes",
    tags=["Billing"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_NOTE_ID_PATH: Final = Path(
    description="Target note product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_USER_ID_PATH: Final = Path(
    description="Target user's UUID — the grant recipient.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)


class PlanLimitsSchema(BaseModel):
    """Per-plan resource caps."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"storage_bytes_max": 2147483648}]},
    )

    storage_bytes_max: int = Field(
        description=(
            "Maximum aggregate storage in bytes for files referenced "
            "from the user's own notes. Files referenced from "
            "multiple blocks count once."
        ),
        examples=[2147483648, 53687091200],
    )


class PlanInfoSchema(BaseModel):
    """In-code plan registry projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "FREE",
                    "name": "Free",
                    "limits": {"storage_bytes_max": 2147483648},
                },
            ],
        },
    )

    code: str = Field(
        description=(
            "Plan identifier — stable token (`FREE`, `BETA`, ...). "
            "Free-tier users without an active subscription row see "
            "`FREE`."
        ),
        examples=["FREE", "BETA"],
    )
    name: str = Field(
        description="Human-readable plan name.",
        examples=["Free", "Beta"],
    )
    limits: PlanLimitsSchema


class StorageUsageSchema(BaseModel):
    """Aggregate storage consumption for the caller."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"storage_bytes": 1879048192}]},
    )

    storage_bytes: int = Field(
        description="Total bytes used across the caller's own notes.",
        examples=[0, 1879048192],
    )


class MySubscriptionSchema(BaseModel):
    """Response for ``GET /users/me/subscription``.

    ``expires_at`` is `null` when the user is on the in-code default
    plan or when their active subscription was granted indefinitely.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "plan": {
                        "code": "FREE",
                        "name": "Free",
                        "limits": {"storage_bytes_max": 2147483648},
                    },
                    "used": {"storage_bytes": 1879048192},
                    "expires_at": None,
                },
            ],
        },
    )

    plan: PlanInfoSchema
    used: StorageUsageSchema
    expires_at: str | None = Field(
        default=None,
        description=(
            "ISO 8601 timestamp with timezone — when the active grant "
            "expires; `null` if indefinite or no active subscription."
        ),
        examples=[None, "2026-12-31T23:59:59+00:00"],
    )


@router.get(
    "",
    summary="Read the caller's current subscription",
    operation_id="getMySubscription",
    dependencies=_AUTH_SECURITY,
    response_model=MySubscriptionSchema,
    error_map=AUTHENTICATED_MAP,
)
async def get_my_subscription(
    request: Request,
    interactor: FromDishka[GetMySubscriptionQueryHandler],
    auth: FromDishka[Authenticator],
) -> MySubscriptionSchema:
    """Return the caller's plan, current storage usage, and expiry.

    Args:
        request: Source of the access cookie.
        interactor: Injected query handler.
        auth: Injected authenticator.

    Returns:
        ``200 OK`` with :class:`MySubscriptionSchema`.

    Raises:
        InvalidTokenError: HTTP 401 — missing or denied access cookie.
    """
    ctx = await auth.authenticate(request)
    view = await interactor.run(
        GetMySubscriptionQuery(actor_id=ctx.user_id),
    )
    return MySubscriptionSchema(
        plan=PlanInfoSchema(
            code=view.plan.code,
            name=view.plan.name,
            limits=PlanLimitsSchema(
                storage_bytes_max=view.plan.limits.storage_bytes_max,
            ),
        ),
        used=StorageUsageSchema(storage_bytes=view.used.storage_bytes),
        expires_at=(
            view.expires_at.isoformat()
            if view.expires_at is not None
            else None
        ),
    )


class NoteStorageRemainingSchema(BaseModel):
    """Response for ``GET /notes/{note_id}/storage-remaining``.

    All four numbers describe the *note author's* quota — a
    collaborator editing the note sees the same headroom the
    author would. ``storage_bytes_remaining`` is clamped to 0; if
    the author is currently over quota (e.g. after a plan
    downgrade) the SPA still gets a non-negative integer to compare
    against the next planned upload size.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "plan_code": "FREE",
                    "storage_bytes_max": 2147483648,
                    "storage_bytes_used": 1879048192,
                    "storage_bytes_remaining": 268435456,
                },
            ],
        },
    )

    plan_code: str = Field(
        description=(
            "Plan code of the **note author** — the quota owner."
        ),
        examples=["FREE", "BETA"],
    )
    storage_bytes_max: int = Field(
        description=(
            "Plan cap in bytes for the note author's storage pool."
        ),
        examples=[2147483648],
    )
    storage_bytes_used: int = Field(
        description=(
            "Bytes currently used across **all** of the note "
            "author's products (not just this note). Files "
            "referenced by multiple blocks count once."
        ),
        examples=[1879048192],
    )
    storage_bytes_remaining: int = Field(
        description=(
            "How many more bytes can be uploaded into this note "
            "before the author's quota is hit. Computed as "
            "``max(0, storage_bytes_max - storage_bytes_used)``. "
            "**Informational** — the value is re-validated under "
            "an advisory lock when an actual upload is attempted, "
            "so a stale large value may still translate to a 413 "
            "if a parallel upload landed first."
        ),
        examples=[268435456],
        ge=0,
    )


@note_router.get(
    "/{note_id}/storage-remaining",
    summary="How many more bytes can be uploaded into this note",
    operation_id="getNoteStorageRemaining",
    dependencies=_AUTH_SECURITY,
    response_model=NoteStorageRemainingSchema,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def get_note_storage_remaining(
    request: Request,
    interactor: FromDishka[GetNoteStorageRemainingQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: UUID = _NOTE_ID_PATH,
) -> NoteStorageRemainingSchema:
    """Report the *note author's* free storage headroom for this note.

    Quota is anchored on the product author, not the actor. A
    collaborator and the author calling this endpoint on the same
    note get the same numbers — they share one quota pool. The
    actor must hold ``EDIT_LESSONS`` on the note (same gate as
    the file-block upload commands).

    Args:
        request: Source of the access cookie.
        interactor: Injected query handler.
        auth: Injected authenticator.
        note_id: UUID of the note product to read for.

    Returns:
        ``200 OK`` with :class:`NoteStorageRemainingSchema`.

    Raises:
        InvalidTokenError: HTTP 401 — missing or denied access cookie.
        EntityNotFoundError: HTTP 404 — no such note.
        InsufficientPermissionsError: HTTP 403 — actor lacks
            ``EDIT_LESSONS`` on the note.
        FieldError: HTTP 422 — malformed input (unlikely for a
            UUID path param, mapped for completeness).
    """
    ctx = await auth.authenticate(request)
    view: NoteStorageRemainingView = await interactor.run(
        GetNoteStorageRemainingQuery(
            actor_id=ctx.user_id,
            note_id=ProductID(note_id),
        ),
    )
    return NoteStorageRemainingSchema(
        plan_code=view.plan_code,
        storage_bytes_max=view.storage_bytes_max,
        storage_bytes_used=view.storage_bytes_used,
        storage_bytes_remaining=view.storage_bytes_remaining,
    )


class NoteStorageSchema(BaseModel):
    """Response for ``GET /notes/{note_id}/storage``.

    The editor's storage card in one read: how many bytes THIS
    note's files occupy plus the author's whole-pool numbers. The
    pool fields match ``NoteStorageRemainingSchema`` exactly; the
    live counterpart with the same shape is
    ``WS /notes/{note_id}/storage`` (see ``## WebSocket
    channels``), which pushes a ``snapshot`` on connect — poll-free
    SPAs can skip this endpoint entirely.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "plan_code": "FREE",
                    "note_storage_bytes_used": 367001600,
                    "storage_bytes_max": 2147483648,
                    "storage_bytes_used": 1879048192,
                    "storage_bytes_remaining": 268435456,
                },
            ],
        },
    )

    plan_code: str = Field(
        description=(
            "Plan code of the **note author** — the quota owner."
        ),
        examples=["FREE", "BETA"],
    )
    note_storage_bytes_used: int = Field(
        description=(
            "Bytes occupied by files referenced from THIS note's "
            "blocks only (file / video-file / photo-collage; "
            "deduplicated, soft-deleted excluded, cover not "
            "counted). Always <= ``storage_bytes_used``."
        ),
        examples=[367001600],
        ge=0,
    )
    storage_bytes_max: int = Field(
        description=(
            "Plan cap in bytes for the note author's storage pool."
        ),
        examples=[2147483648],
    )
    storage_bytes_used: int = Field(
        description=(
            "Bytes currently used across **all** of the note "
            "author's products (not just this note). Files "
            "referenced by multiple blocks count once."
        ),
        examples=[1879048192],
    )
    storage_bytes_remaining: int = Field(
        description=(
            "How many more bytes can be uploaded before the "
            "author's quota is hit. Computed as ``max(0, "
            "storage_bytes_max - storage_bytes_used)``. "
            "**Informational** — re-validated under an advisory "
            "lock when an actual upload is attempted."
        ),
        examples=[268435456],
        ge=0,
    )


@note_router.get(
    "/{note_id}/storage",
    summary="This note's storage usage plus the author's pool headroom",
    operation_id="getNoteStorage",
    dependencies=_AUTH_SECURITY,
    response_model=NoteStorageSchema,
    error_map=AUTHENTICATED_AUTHORIZED_FIELD_MAP,
)
async def get_note_storage(
    request: Request,
    interactor: FromDishka[GetNoteStorageQueryHandler],
    auth: FromDishka[Authenticator],
    note_id: UUID = _NOTE_ID_PATH,
) -> NoteStorageSchema:
    """Report this note's usage and the author's pool in one read.

    Quota is anchored on the product author, not the actor. A
    collaborator and the author calling this endpoint on the same
    note get the same numbers — they share one quota pool. The
    actor must hold ``EDIT_LESSONS`` on the note (same gate as
    the file-block upload commands).

    Args:
        request: Source of the access cookie.
        interactor: Injected query handler.
        auth: Injected authenticator.
        note_id: UUID of the note product to read for.

    Returns:
        ``200 OK`` with :class:`NoteStorageSchema`.

    Raises:
        InvalidTokenError: HTTP 401 — missing or denied access cookie.
        EntityNotFoundError: HTTP 404 — no such note.
        InsufficientPermissionsError: HTTP 403 — actor lacks
            ``EDIT_LESSONS`` on the note.
        FieldError: HTTP 422 — malformed input (unlikely for a
            UUID path param, mapped for completeness).
    """
    ctx = await auth.authenticate(request)
    view: NoteStorageView = await interactor.run(
        GetNoteStorageQuery(
            actor_id=ctx.user_id,
            note_id=ProductID(note_id),
        ),
    )
    return NoteStorageSchema(
        plan_code=view.plan_code,
        note_storage_bytes_used=view.note_storage_bytes_used,
        storage_bytes_max=view.storage_bytes_max,
        storage_bytes_used=view.storage_bytes_used,
        storage_bytes_remaining=view.storage_bytes_remaining,
    )


# ------------------------- admin grant / revoke ------------------------ #


class GrantSubscriptionSchema(BaseModel):
    """Body for ``POST /admin/users/{user_id}/subscription``.

    Both fields are optional. ``plan_code`` defaults to ``BETA`` —
    the upgraded free-access tier the endpoint exists to hand out;
    pass any code present in the in-code registry
    (`learnic/entities/billing/plan.py`). ``expires_at`` defaults to
    `null`, granting the plan indefinitely; pass a future,
    timezone-aware ISO 8601 timestamp to time-box the grant.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"plan_code": "BETA", "expires_at": None},
                {
                    "plan_code": "BETA",
                    "expires_at": "2026-12-31T23:59:59+00:00",
                },
            ],
        },
    )

    plan_code: str = Field(
        default=BETA,
        description=(
            "Plan code to grant — a token from the in-code plan "
            "registry (`FREE`, `BETA`, ...). Defaults to `BETA`. "
            f"Max length {PLAN_CODE_MAX_LEN} (`PLAN_CODE_MAX_LEN`). "
            "An unknown code is rejected with 422 `UnknownPlanCode`."
        ),
        min_length=1,
        max_length=PLAN_CODE_MAX_LEN,
        examples=["BETA", "FREE"],
    )
    expires_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "When the grant lapses, as a timezone-aware ISO 8601 "
            "timestamp. `null` (the default) grants the plan "
            "indefinitely. Must be in the future — a past or present "
            "value is rejected with 422 "
            "`SubscriptionExpiryInPastError`."
        ),
        examples=[None, "2026-12-31T23:59:59+00:00"],
    )


class GrantedSubscriptionSchema(BaseModel):
    """Response for ``POST /admin/users/{user_id}/subscription``.

    The freshly-minted grant joined with the in-code plan it points
    at, so the admin UI can render the resulting "tariff card"
    without a follow-up read. ``expires_at`` is `null` for an
    indefinite grant; ``granted_by`` is the acting administrator.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "subscription_id": (
                        "7c9e6679-7425-40de-944b-e07fc1f90ae7"
                    ),
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "plan": {
                        "code": "BETA",
                        "name": "Beta",
                        "limits": {"storage_bytes_max": 53687091200},
                    },
                    "granted_at": "2026-06-12T10:00:00+00:00",
                    "expires_at": None,
                    "granted_by": (
                        "9b2f5a10-1c3d-4e5f-8a7b-2c3d4e5f6a7b"
                    ),
                },
            ],
        },
    )

    subscription_id: UUID = Field(
        description="UUID of the newly-created subscription grant row.",
        examples=["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
    )
    user_id: UUID = Field(
        description="UUID of the user the grant was issued to.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    plan: PlanInfoSchema
    granted_at: datetime = Field(
        description=(
            "ISO 8601 timestamp with timezone — when the grant was "
            "issued (server time, UTC)."
        ),
        examples=["2026-06-12T10:00:00+00:00"],
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "ISO 8601 timestamp with timezone — when the grant "
            "expires; `null` if granted indefinitely."
        ),
        examples=[None, "2026-12-31T23:59:59+00:00"],
    )
    granted_by: UUID | None = Field(
        default=None,
        description=(
            "UUID of the administrator who issued the grant; `null` "
            "if that admin's account was since deleted."
        ),
        examples=["9b2f5a10-1c3d-4e5f-8a7b-2c3d4e5f6a7b"],
    )

    @classmethod
    def from_result(cls, result: GrantedSubscription) -> Self:
        return cls(
            subscription_id=result.oid,
            user_id=result.user_id,
            plan=PlanInfoSchema(
                code=result.plan.code,
                name=result.plan.name,
                limits=PlanLimitsSchema(
                    storage_bytes_max=result.plan.limits.storage_bytes_max,
                ),
            ),
            granted_at=result.granted_at,
            expires_at=result.expires_at,
            granted_by=result.granted_by,
        )


@admin_router.post(
    "/{user_id}/subscription",
    summary="Grant a user free access to a tariff",
    operation_id="grantUserSubscription",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=GrantedSubscriptionSchema,
    error_map=SUBSCRIPTION_GRANT_MAP,
)
async def grant_user_subscription(
    request: Request,
    payload: GrantSubscriptionSchema,
    interactor: FromDishka[GrantSubscriptionCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    user_id: UUID = _USER_ID_PATH,
) -> GrantedSubscriptionSchema:
    """Grant a user a tariff free of charge (e.g. add them to BETA).

    Admin-only. Appends a fresh subscription grant row stamped with
    the acting admin as ``granted_by``; the user's "current" plan
    becomes the most recent active grant, so re-granting with a new
    expiry extends or replaces access without erasing history. Use
    ``DELETE`` on the same path to drop the user back to FREE.

    Args:
        request: Source of the access-token cookie.
        payload: Plan code to grant (defaults to `BETA`) and an
            optional future expiry (defaults to indefinite).
        interactor: Injected grant-subscription command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with :class:`GrantedSubscriptionSchema`
        describing the new grant and its resolved plan.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No user with the given id; HTTP 404.
        UnknownPlanCodeError: ``plan_code`` is not in the registry;
            HTTP 422 via `UNKNOWN_PLAN_CODE_RULE`.
        SubscriptionExpiryInPastError: ``expires_at`` is not in the
            future; HTTP 422 via `FIELD_ERROR_RULE`.
    """
    ctx = await admin_auth.authenticate_admin(request)
    result = await interactor.run(
        GrantSubscriptionCommand(
            actor_id=ctx.user_id,
            user_id=UserID(user_id),
            plan_code=PlanCode(payload.plan_code),
            expires_at=payload.expires_at,
        ),
    )
    return GrantedSubscriptionSchema.from_result(result)


@admin_router.delete(
    "/{user_id}/subscription",
    summary="Revoke a user's tariff, returning them to FREE",
    operation_id="revokeUserSubscription",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=ADMIN_MAP,
)
async def revoke_user_subscription(
    request: Request,
    interactor: FromDishka[RevokeSubscriptionCommandHandler],
    admin_auth: FromDishka[AdminAuthenticator],
    user_id: UUID = _USER_ID_PATH,
) -> None:
    """Revoke every active grant a user holds, dropping them to FREE.

    Admin-only and **idempotent**: it stamps ``revoked_at`` on all of
    the user's currently-active grants (preserving the audit trail).
    A user already on FREE has nothing to revoke and the call still
    succeeds with ``204``. The inverse of ``POST`` on the same path.

    Args:
        request: Source of the access-token cookie.
        interactor: Injected revoke-subscription command handler.
        admin_auth: Injected authenticator that validates the access
            cookie and asserts the platform-admin flag.
        user_id: Target user's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotAdminError: Caller is not a platform admin; HTTP 403.
        EntityNotFoundError: No user with the given id; HTTP 404.
    """
    await admin_auth.authenticate_admin(request)
    await interactor.run(RevokeSubscriptionCommand(user_id=UserID(user_id)))
