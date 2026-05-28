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
    RePinCourseEnrollmentCommand,
    RePinCourseEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.update_progress import (
    UpdateProgressCommand,
    UpdateProgressCommandHandler,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentView,
)
from learnic.application.queries.enrollment.list_for_student import (
    GetStudentEnrollmentsQuery,
    GetStudentEnrollmentsQueryHandler,
)
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
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

course_router = ErrorAwareRouter(
    prefix="/courses/{course_id}/enrollments",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/enrollments",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COURSE_ID_PATH: Final = Path(
    description="Parent course (product) UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_ENROLLMENT_ID_PATH: Final = Path(
    description="Target enrollment UUID.",
    examples=["e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8"],
)


# --------------------------- request / response schemas --------------- #


class UpdateProgressSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/enrollments/{id}/progress``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": 75}]},
    )

    value: int = Field(
        ge=PROGRESS_PERCENT_MIN,
        le=PROGRESS_PERCENT_MAX,
        description=(
            "New progress percentage in "
            f"`[{PROGRESS_PERCENT_MIN}, {PROGRESS_PERCENT_MAX}]`. "
            f"Setting `{PROGRESS_PERCENT_MAX}` automatically marks "
            "the enrollment completed (sets `completed_at` on the "
            "course details body; does not change `status`)."
        ),
        examples=[75],
    )


class RePinEnrollmentSchema(BaseModel):
    """Body for ``PATCH /courses/{course_id}/enrollments/{id}/release``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"release_id": "7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"},
            ],
        },
    )

    release_id: UUID = Field(
        description=(
            "Target release UUID. Must belong to the same course "
            "as the enrollment — releases of other products are "
            "rejected as `EntityNotFound`."
        ),
        examples=["7a8b9c0d-1e2f-4a3b-9c4d-5e6f7a8b9c0d"],
    )


class CourseEnrollmentDetailsSchema(BaseModel):
    """Course-kind specific projection of an :class:`EnrollmentView`."""

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

    ``kind`` discriminates the polymorphic body: ``course``
    enrollments carry ``details`` shaped as
    :class:`CourseEnrollmentDetailsSchema`. ``product_id`` and
    ``student_id`` live on the base shape so callers don't have
    to descend into ``details`` for the most common references.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8",
                    "kind": "course",
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
    details: CourseEnrollmentDetailsSchema | None

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
                CourseEnrollmentDetailsSchema(
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


# --------------------------- course item ops -------------------------- #


@course_router.patch(
    "/{enrollment_id}/progress",
    summary="Update progress on a course enrollment",
    operation_id="updateEnrollmentProgress",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_progress(
    request: Request,
    payload: UpdateProgressSchema,
    interactor: FromDishka[UpdateProgressCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Update progress (student-only). Hitting 100 auto-completes.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: Caller is not the enrolled
            student; HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: ``ProgressPercent`` invariants; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateProgressCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
            progress_percent=payload.value,
        ),
    )


@course_router.post(
    "/{enrollment_id}/complete",
    summary="Mark a course enrollment completed",
    operation_id="completeCourseEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete_course(
    request: Request,
    interactor: FromDishka[CompleteEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Mark a course enrollment completed (product author only).

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


@course_router.patch(
    "/{enrollment_id}/release",
    summary="Re-pin a course enrollment to a different release",
    operation_id="repinCourseEnrollment",
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
    interactor: FromDishka[RePinCourseEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Move a course enrollment to a different release (author only).

    Caller needs ``MANAGE_RELEASES`` on the parent product (owner
    short-circuits inside the authorizer). The target release
    must belong to the same course as the enrollment. Only
    ACTIVE enrollments may be re-pinned — revoked enrollments
    have no access and must be restored first.

    The strict-pinning policy still holds for new and existing
    enrollments: students never auto-upgrade. This endpoint is
    the explicit escape hatch for authors to roll a cohort onto
    a hotfix release or pull a student back to an older
    version of the material.

    Args:
        payload: Body carrying the target ``release_id``.
        course_id: Parent course (product) UUID — present for
            URL framing, not used by the handler (validation
            walks ``enrollment → product → release``).
        enrollment_id: Target enrollment UUID.

    Returns:
        ``204 No Content`` on success.

    Raises:
        InvalidTokenError: HTTP 401.
        InsufficientPermissionsError: HTTP 403 — caller lacks
            ``MANAGE_RELEASES`` on the course.
        EntityNotFoundError: HTTP 404 — enrollment missing, or
            target release missing / belongs to a different
            product.
        EnrollmentDoesNotSupportError: HTTP 409 — enrollment
            kind has no release pin (only ``course`` kind does
            today).
        CannotRepinRevokedEnrollmentError: HTTP 409 — enrollment
            is REVOKED.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RePinCourseEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
            release_id=CourseReleaseID(payload.release_id),
        ),
    )
