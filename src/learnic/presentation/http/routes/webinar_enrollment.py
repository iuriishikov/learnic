from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict

from learnic.application.commands.webinar_enrollment.complete import (
    CompleteWebinarEnrollmentCommand,
    CompleteWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.drop import (
    DropWebinarEnrollmentCommand,
    DropWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.refund import (
    RefundWebinarEnrollmentCommand,
    RefundWebinarEnrollmentCommandHandler,
)
from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentView,
)
from learnic.application.queries.webinar_enrollment.list_for_student import (
    GetStudentWebinarEnrollmentsQuery,
    GetStudentWebinarEnrollmentsQueryHandler,
)
from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID
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
    prefix="/cohorts/{cohort_id}/enrollments",
    tags=["WebinarEnrollments"],
    route_class=DishkaErrorAwareRoute,
)
me_router = ErrorAwareRouter(
    prefix="/users/me/webinar-enrollments",
    tags=["WebinarEnrollments"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COHORT_ID_PATH: Final = Path(
    description="Parent cohort UUID.",
    examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
)
_ENROLLMENT_ID_PATH: Final = Path(
    description="Target webinar enrollment UUID.",
    examples=["d4e5f607-1a23-4d2c-9d11-9d4f0a44b6c8"],
)


class WebinarEnrollmentSchema(BaseModel):
    """Webinar enrollment response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "d4e5f607-1a23-4d2c-9d11-9d4f0a44b6c8",
                    "cohort_id": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8",
                    "student_id": ("550e8400-e29b-41d4-a716-446655440000"),
                    "status": "active",
                    "enrolled_at": "2026-04-29T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID
    cohort_id: UUID
    student_id: UUID
    status: WebinarEnrollmentStatus
    enrolled_at: datetime

    @classmethod
    def from_view(cls, view: WebinarEnrollmentView) -> Self:
        return cls(
            oid=view.oid,
            cohort_id=view.cohort_id,
            student_id=view.student_id,
            status=view.status,
            enrolled_at=view.enrolled_at,
        )


@me_router.get(
    "",
    summary="List the current user's webinar enrollments",
    operation_id="getMyWebinarEnrollments",
    response_model=list[WebinarEnrollmentSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_WITH_FIELD_MAP,
)
async def get_mine(
    request: Request,
    interactor: FromDishka[GetStudentWebinarEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
) -> list[WebinarEnrollmentSchema]:
    """Return enrollments of the current user, newest first.

    Raises:
        InvalidTokenError: HTTP 401.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetStudentWebinarEnrollmentsQuery(student_id=ctx.user_id),
    )
    return [WebinarEnrollmentSchema.from_view(v) for v in views]


@router.post(
    "/{enrollment_id}/drop",
    summary="Drop a webinar enrollment",
    operation_id="dropWebinarEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def drop(
    request: Request,
    interactor: FromDishka[DropWebinarEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    enrollment_id: UUID = _ENROLLMENT_ID_PATH,
) -> None:
    """Mark the enrollment as dropped.

    Authorised actors: the enrolled student themselves, the cohort
    host, or the parent product author.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DropWebinarEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=WebinarEnrollmentID(enrollment_id),
        ),
    )


@router.post(
    "/{enrollment_id}/complete",
    summary="Mark a webinar enrollment completed",
    operation_id="completeWebinarEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete(
    request: Request,
    interactor: FromDishka[CompleteWebinarEnrollmentCommandHandler],
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
        CompleteWebinarEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=WebinarEnrollmentID(enrollment_id),
        ),
    )


@router.post(
    "/{enrollment_id}/refund",
    summary="Mark a webinar enrollment refunded",
    operation_id="refundWebinarEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def refund(
    request: Request,
    interactor: FromDishka[RefundWebinarEnrollmentCommandHandler],
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
        RefundWebinarEnrollmentCommand(
            actor_id=ctx.user_id,
            enrollment_id=WebinarEnrollmentID(enrollment_id),
        ),
    )
