from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.enrollment.complete import (
    CompleteEnrollmentCommand,
    CompleteEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.repin import (
    RePinNoteEnrollmentCommand,
    RePinNoteEnrollmentCommandHandler,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentView,
)
from learnic.application.queries.enrollment.list_for_student import (
    GetStudentEnrollmentsQuery,
    GetStudentEnrollmentsQueryHandler,
)
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.enrollment.enums import (
    EnrollmentKind,
    EnrollmentStatus,
)
from learnic.entities.enrollment.errors import (
    CannotRepinRevokedEnrollmentError,
    EnrollmentDoesNotSupportError,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    CANNOT_REPIN_REVOKED_ENROLLMENT_RULE,
    ENROLLMENT_DOES_NOT_SUPPORT_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

note_router = ErrorAwareRouter(
    prefix="/notes/{note_id}/enrollments",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/enrollments",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_NOTE_ID_PATH: Final = Path(
    description="Parent note (product) UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_ENROLLMENT_ID_PATH: Final = Path(
    description="Target enrollment UUID.",
    examples=["e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8"],
)


# --------------------------- request / response schemas --------------- #


class RePinEnrollmentSchema(BaseModel):
    """Body for ``PATCH /notes/{note_id}/enrollments/{id}/release``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"},
            ],
        },
    )

    release_id: UUID = Field(
        description=(
            "Target release UUID. Must belong to the same note "
            "as the enrollment — releases of other products are "
            "rejected as `EntityNotFound`."
        ),
        examples=["7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"],
    )


class NoteEnrollmentDetailsSchema(BaseModel):
    """Note-kind specific projection of an :class:`EnrollmentView`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "release_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
                    "progress_percent": 0,
                    "completed_at": None,
                },
            ],
        },
    )

    release_id: UUID | None
    progress_percent: int
    completed_at: datetime | None


class EnrollmentSchema(BaseModel):
    """Unified response projection for :class:`EnrollmentView`.

    ``kind`` discriminates the polymorphic body: ``note``
    enrollments carry ``details`` shaped as
    :class:`NoteEnrollmentDetailsSchema`. ``product_id`` and
    ``student_id`` live on the base shape so callers don't have
    to descend into ``details`` for the most common references.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8",
                    "kind": "note",
                    "product_id": (
                        "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"
                    ),
                    "student_id": (
                        "550e8400-e29b-41d4-a716-446655440000"
                    ),
                    "status": "active",
                    "enrolled_at": "2026-04-29T10:00:00+00:00",
                    "details": {
                        "release_id": (
                            "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
                        ),
                        "progress_percent": 0,
                        "completed_at": None,
                    },
                },
            ],
        },
    )

    oid: UUID
    kind: EnrollmentKind
    product_id: UUID
    student_id: UUID
    status: EnrollmentStatus
    enrolled_at: datetime
    details: NoteEnrollmentDetailsSchema | None

    @classmethod
    def from_view(cls, view: EnrollmentView) -> Self:
        return cls(
            oid=view.oid,
            kind=view.kind,
            product_id=view.product_id,
            student_id=view.student_id,
            status=view.status,
            enrolled_at=view.enrolled_at,
            details=(
                NoteEnrollmentDetailsSchema(
                    release_id=view.details.release_id,
                    progress_percent=view.details.progress_percent,
                    completed_at=view.details.completed_at,
                )
                if view.details is not None
                else None
            ),
        )


# ------------------------------ caller-scoped ------------------------- #


@me_router.get(
    "",
    summary="List the current user's enrollments",
    operation_id="getMyEnrollments",
    response_model=list[EnrollmentSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def get_mine(
    request: Request,
    interactor: FromDishka[GetStudentEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
) -> list[EnrollmentSchema]:
    """Return all enrollments of the current user, newest first.

    Raises:
        InvalidTokenError: HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetStudentEnrollmentsQuery(student_id=ctx.user_id),
    )
    return [EnrollmentSchema.from_view(v) for v in views]


# --------------------------- note item ops -------------------------- #


@note_router.post(
    "/{enrollment_id}/complete",
    summary="Mark a note enrollment completed",
    operation_id="completeNoteEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete_note(
    request: Request,
    interactor: FromDishka[CompleteEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    note_id: UUID = _NOTE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Mark a note enrollment completed (product author only).

    Sets ``details.completed_at`` on the enrollment. Does NOT
    change ``status`` — a completed enrollment is still ACTIVE.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CompleteEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
        ),
    )


@note_router.patch(
    "/{enrollment_id}/release",
    summary="Re-pin a note enrollment to a different release",
    operation_id="repinNoteEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP
    | {
        EnrollmentDoesNotSupportError: ENROLLMENT_DOES_NOT_SUPPORT_RULE,
        CannotRepinRevokedEnrollmentError: (
            CANNOT_REPIN_REVOKED_ENROLLMENT_RULE
        ),
    },
)
async def repin_release(
    request: Request,
    payload: RePinEnrollmentSchema,
    interactor: FromDishka[RePinNoteEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    note_id: UUID = _NOTE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Move a note enrollment to a different release (author only).

    Caller needs ``MANAGE_RELEASES`` on the parent product (owner
    short-circuits inside the authorizer). The target release
    must belong to the same note as the enrollment. Only
    ACTIVE enrollments may be re-pinned — revoked enrollments
    have no access and must be restored first.

    The strict-pinning policy still holds for new and existing
    enrollments: students never auto-upgrade. This endpoint is
    the explicit escape hatch for authors to roll a cohort onto
    a hotfix release or pull a student back to an older
    version of the material.

    Args:
        payload: Body carrying the target ``release_id``.
        note_id: Parent note (product) UUID — present for
            URL framing, not used by the handler (validation
            walks ``enrollment → product → release``).
        enrollment_id: Target enrollment UUID.

    Returns:
        ``204 No Content`` on success.

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller lacks
            ``MANAGE_RELEASES`` on the note.
        EntityNotFoundError: HTTP 404 — enrollment missing, or
            target release missing / belongs to a different
            product.
        EnrollmentDoesNotSupportError: HTTP 409 — enrollment
            kind has no release pin (only ``note`` kind does
            today).
        CannotRepinRevokedEnrollmentError: HTTP 409 — enrollment
            is REVOKED.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RePinNoteEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
            release_id=NoteReleaseID(payload.release_id),
        ),
    )
