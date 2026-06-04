"""HTTP routes for billing — caller-scoped subscription read.

Future admin grants ("POST /admin/users/{id}/subscription") and a
history-listing endpoint will land in this module alongside the
current read, sharing the ``Billing`` aggregate tag.

Two routers ship here:

* ``router`` — ``/users/me/subscription`` for the caller-scoped read
  (CLAUDE.md rule 14: "everything about the authenticated user" is
  namespaced under ``/users/me/...``).
* ``note_router`` — ``/notes/{note_id}/storage-remaining``
  nests under the parent note (rule 14: sub-resources mirror the
  aggregate tree). The endpoint reports the *note author's* free
  bytes so a collaborator opening an editor sees the same number
  the author would; both share one quota pool.
"""

from typing import Final
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.queries.billing.get_note_storage_remaining import (
    NoteStorageRemainingView,
    GetNoteStorageRemainingQuery,
    GetNoteStorageRemainingQueryHandler,
)
from learnic.application.queries.billing.get_my_subscription import (
    GetMySubscriptionQuery,
    GetMySubscriptionQueryHandler,
)
from learnic.entities.product.ids import ProductID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_AUTHORIZED_FIELD_MAP,
    AUTHENTICATED_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/users/me/subscription",
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
