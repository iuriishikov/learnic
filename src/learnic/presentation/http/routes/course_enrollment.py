from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.course_enrollment.complete import (
    CompleteCourseEnrollmentCommand,
    CompleteCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_enrollment.refund import (
    RefundCourseEnrollmentCommand,
    RefundCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_enrollment.update_progress import (
    UpdateCourseProgressCommand,
    UpdateCourseProgressCommandHandler,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentView,
)
from learnic.application.queries.course_enrollment.list_for_student import (
    GetStudentCourseEnrollmentsQuery,
    GetStudentCourseEnrollmentsQueryHandler,
)
from learnic.entities.course_enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/courses/{course_id}/enrollments",
    tags=["CourseEnrollments"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/course-enrollments",
    tags=["CourseEnrollments"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COURSE_ID_PATH: Final = Path(
    description="Parent course (product) UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)
_ENROLLMENT_ID_PATH: Final = Path(
    description="Target course enrollment UUID.",
    examples=["e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8"],
)


class UpdateCourseProgressSchema(BaseModel):
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


class CourseEnrollmentSchema(BaseModel):
    """Course enrollment response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "e5f60718-2b34-4d2c-9d11-9d4f0a44b6c8",
                    "product_id": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "student_id": ("550e8400-e29b-41d4-a716-446655440000"),
                    "status": "active",
                    "progress_percent": 0,
                    "enrolled_at": "2026-04-29T10:00:00+00:00",
                    "completed_at": None,
                },
            ],
        },
    )

    oid: UUID
    product_id: UUID
    student_id: UUID
    status: CourseEnrollmentStatus
    progress_percent: int
    enrolled_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_view(cls, view: CourseEnrollmentView) -> Self:
        return cls(
            oid=view.oid,
            product_id=view.product_id,
            student_id=view.student_id,
            status=view.status,
            progress_percent=view.progress_percent,
            enrolled_at=view.enrolled_at,
            completed_at=view.completed_at,
        )


@me_router.get(
    "",
    summary="List the current user's course enrollments",
    operation_id="getMyCourseEnrollments",
    response_model=list[CourseEnrollmentSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def get_mine(
    request: Request,
    interactor: FromDishka[GetStudentCourseEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
) -> list[CourseEnrollmentSchema]:
    """Return course enrollments of the current user, newest first.

    Raises:
        InvalidTokenError: HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetStudentCourseEnrollmentsQuery(student_id=ctx.user_id),
    )
    return [CourseEnrollmentSchema.from_view(v) for v in views]


@router.patch(
    "/{enrollment_id}/progress",
    summary="Update progress on a course enrollment",
    operation_id="updateCourseProgress",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_progress(
    request: Request,
    payload: UpdateCourseProgressSchema,
    interactor: FromDishka[UpdateCourseProgressCommandHandler],
    auth: FromDishka[Authenticator],
    course_id: UUID = _COURSE_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Update progress (student-only). Hitting 100 auto-completes.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: Caller is not the enrolled student;
            HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: ``ProgressPercent`` invariants; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCourseProgressCommand(
            actor_id=ctx.user_id,
            enrollment_id=CourseEnrollmentID(enrollment_id),
            progress_percent=payload.value,
        ),
    )


@router.post(
    "/{enrollment_id}/complete",
    summary="Mark a course enrollment completed",
    operation_id="completeCourseEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete(
    request: Request,
    interactor: FromDishka[CompleteCourseEnrollmentCommandHandler],
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
        CompleteCourseEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=CourseEnrollmentID(enrollment_id),
        ),
    )


@router.post(
    "/{enrollment_id}/refund",
    summary="Mark a course enrollment refunded",
    operation_id="refundCourseEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def refund(
    request: Request,
    interactor: FromDishka[RefundCourseEnrollmentCommandHandler],
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
        RefundCourseEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=CourseEnrollmentID(enrollment_id),
        ),
    )
