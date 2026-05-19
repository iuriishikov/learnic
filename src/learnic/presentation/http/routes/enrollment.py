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
from learnic.application.commands.enrollment.refund import (
    RefundEnrollmentCommand,
    RefundEnrollmentCommandHandler,
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
from learnic.entities.enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

course_router = ErrorAwareRouter(
    prefix="/courses/{course_id}/enrollments",
    tags=["Enrollments"],
    route_class=DishkaErrorAwareRoute,
)
webinar_router = ErrorAwareRouter(
    prefix="/cohorts/{cohort_id}/enrollments",
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
_COHORT_ID_PATH: Final = Path(
    description="Parent cohort UUID.",
    examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
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
            "the enrollment completed."
        ),
        examples=[75],
    )


class CourseDetailsSchema(BaseModel):
    """Course-specific projection of an :class:`EnrollmentView`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_id": "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8",
                    "release_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
                    "progress_percent": 0,
                    "completed_at": None,
                },
            ],
        },
    )

    product_id: UUID
    release_id: UUID | None
    progress_percent: int
    completed_at: datetime | None


class WebinarDetailsSchema(BaseModel):
    """Webinar-specific projection of an :class:`EnrollmentView`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"cohort_id": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    cohort_id: UUID


class EnrollmentSchema(BaseModel):
    """Unified response projection for :class:`EnrollmentView`.

    Exactly one of ``course_details`` / ``webinar_details`` is
    populated, matching ``type``. SPA discriminates on ``type``.
    Replaces the previous ``CourseEnrollmentSchema`` and
    ``WebinarEnrollmentSchema`` from the split world.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8",
                    "type": "course",
                    "student_id": (
                        "550e8400-e29b-41d4-a716-446655440000"
                    ),
                    "status": "active",
                    "enrolled_at": "2026-04-29T10:00:00+00:00",
                    "course_details": {
                        "product_id": (
                            "3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"
                        ),
                        "release_id": (
                            "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
                        ),
                        "progress_percent": 0,
                        "completed_at": None,
                    },
                    "webinar_details": None,
                },
            ],
        },
    )

    oid: UUID
    type: EnrollmentType
    student_id: UUID
    status: EnrollmentStatus
    enrolled_at: datetime
    course_details: CourseDetailsSchema | None
    webinar_details: WebinarDetailsSchema | None

    @classmethod
    def from_view(cls, view: EnrollmentView) -> Self:
        return cls(
            oid=view.oid,
            type=view.type,
            student_id=view.student_id,
            status=view.status,
            enrolled_at=view.enrolled_at,
            course_details=(
                CourseDetailsSchema(
                    product_id=view.course_details.product_id,
                    release_id=view.course_details.release_id,
                    progress_percent=(
                        view.course_details.progress_percent
                    ),
                    completed_at=view.course_details.completed_at,
                )
                if view.course_details is not None
                else None
            ),
            webinar_details=(
                WebinarDetailsSchema(
                    cohort_id=view.webinar_details.cohort_id,
                )
                if view.webinar_details is not None
                else None
            ),
        )


# ------------------------------ caller-scoped ------------------------- #


@me_router.get(
    "",
    summary="List the current user's enrollments (both types)",
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

    Returns both course and webinar enrollments unified — SPA
    branches on ``type``. Replaces the previous
    ``GET /users/me/course-enrollments`` and
    ``GET /users/me/webinar-enrollments``.

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

    Course-only; webinar enrollments raise
    ``EnrollmentDoesNotSupportError`` (HTTP 422 via field-error
    family) — though the URL itself nests under ``/courses/``,
    the handler still guards via capability since enrollment id
    is global.

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
    """Set ``status`` to ``completed`` (product author only).

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


@course_router.post(
    "/{enrollment_id}/refund",
    summary="Mark a course enrollment refunded",
    operation_id="refundCourseEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def refund_course(
    request: Request,
    interactor: FromDishka[RefundEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Set ``status`` to ``refunded`` (product author only).

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RefundEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
        ),
    )


# --------------------------- webinar item ops ------------------------- #
# Note: no ``drop`` endpoint — see EnrollmentStatus docstring for the
# migration story. Walk-away semantics now go through refund.


@webinar_router.post(
    "/{enrollment_id}/complete",
    summary="Mark a webinar enrollment completed",
    operation_id="completeWebinarEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete_webinar(
    request: Request,
    interactor: FromDishka[CompleteEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Set ``status`` to ``completed`` (host/author only).

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


@webinar_router.post(
    "/{enrollment_id}/refund",
    summary="Mark a webinar enrollment refunded",
    operation_id="refundWebinarEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def refund_webinar(
    request: Request,
    interactor: FromDishka[RefundEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Set ``status`` to ``refunded`` (host/author only).

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RefundEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=EnrollmentID(enrollment_id),
        ),
    )
