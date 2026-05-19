from datetime import date, datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.cohort.cancel import (
    CancelCohortCommand,
    CancelCohortCommandHandler,
)
from learnic.application.commands.webinar_schedule.add import (
    AddWebinarScheduleCommand,
    AddWebinarScheduleCommandHandler,
)
from learnic.application.commands.enrollment.enroll_in_cohort import (
    EnrollStudentInCohortCommand,
    EnrollStudentInCohortCommandHandler,
)
from learnic.application.commands.webinar_session.add_one_off import (
    AddOneOffWebinarSessionCommand,
    AddOneOffWebinarSessionCommandHandler,
)
from learnic.application.commands.cohort.close_enrollment import (
    CloseCohortEnrollmentCommand,
    CloseCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.complete import (
    CompleteCohortCommand,
    CompleteCohortCommandHandler,
)
from learnic.application.commands.cohort.mark_full import (
    MarkCohortFullCommand,
    MarkCohortFullCommandHandler,
)
from learnic.application.commands.cohort.open_enrollment import (
    OpenCohortEnrollmentCommand,
    OpenCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.reschedule import (
    RescheduleCohortCommand,
    RescheduleCohortCommandHandler,
)
from learnic.application.commands.cohort.start import (
    StartCohortCommand,
    StartCohortCommandHandler,
)
from learnic.application.commands.cohort.update_max_participants import (
    UpdateCohortMaxParticipantsCommand,
    UpdateCohortMaxParticipantsCommandHandler,
)
from learnic.application.commands.cohort.update_name import (
    UpdateCohortNameCommand,
    UpdateCohortNameCommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CohortFullError,
    EnrollmentClosedError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.cohort import CohortView
from learnic.application.queries.enrollment.list_for_cohort import (
    GetCohortEnrollmentsQuery,
    GetCohortEnrollmentsQueryHandler,
)
from learnic.presentation.http.routes.enrollment import (
    EnrollmentSchema,
)
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleView,
)
from learnic.application.common.persistence.webinar_session import (
    WebinarSessionView,
)
from learnic.application.queries.cohort.get import (
    GetCohortQuery,
    GetCohortQueryHandler,
)
from learnic.application.queries.webinar_schedule.list_for_cohort import (
    GetCohortSchedulesQuery,
    GetCohortSchedulesQueryHandler,
)
from learnic.application.queries.webinar_session.list_for_cohort import (
    GetCohortSessionsQuery,
    GetCohortSessionsQueryHandler,
)
from learnic.entities.cohort.constants import (
    COHORT_NAME_MAX_LEN,
    IANA_TIMEZONE_MAX_LEN,
    RRULE_MAX_LEN,
    SESSION_STREAM_URL_MAX_LEN,
)
from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
    WebinarSessionStatus,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.product.constants import (
    WEBINAR_DURATION_MINUTES_MAX,
    WEBINAR_DURATION_MINUTES_MIN,
    WEBINAR_PARTICIPANTS_MIN,
)
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    ALREADY_ENROLLED_RULE,
    AUTHENTICATED_OWNER_FIELD_MAP,
    AUTHENTICATED_WITH_FIELD_MAP,
    COHORT_FULL_RULE,
    ENROLLMENT_CLOSED_RULE,
    ENTITY_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/cohorts",
    tags=["Cohorts"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COHORT_ID_PATH: Final = Path(
    description="Target cohort UUID.",
    examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
)


# ---------------------------- request schemas -------------------------- #


class UpdateCohortNameSchema(BaseModel):
    """Body for ``PATCH /cohorts/{cohort_id}/name``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"value": "Поток №3, осень 2026"}, {"value": None}],
        },
    )

    value: str | None = Field(
        description=(
            "New cohort name, or `null` to clear it. "
            f"Max length is {COHORT_NAME_MAX_LEN} chars "
            "(`COHORT_NAME_MAX_LEN`)."
        ),
        max_length=COHORT_NAME_MAX_LEN,
        examples=["Поток №3, осень 2026", None],
    )


class UpdateCohortMaxParticipantsSchema(BaseModel):
    """Body for ``PATCH /cohorts/{cohort_id}/max-participants``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"value": 30}, {"value": None}]},
    )

    value: int | None = Field(
        description=(
            "Cohort-level cap, or `null` to clear (use webinar's "
            f"default). Minimum {WEBINAR_PARTICIPANTS_MIN}."
        ),
        ge=WEBINAR_PARTICIPANTS_MIN,
        examples=[30, None],
    )


class RescheduleCohortSchema(BaseModel):
    """Body for ``PATCH /cohorts/{cohort_id}/dates``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"starts_on": "2026-09-01", "ends_on": "2026-12-15"},
            ],
        },
    )

    starts_on: date = Field(
        description="New cohort start date (inclusive).",
        examples=["2026-09-01"],
    )
    ends_on: date | None = Field(
        description="New cohort end date (inclusive); `null` = open-ended.",
        examples=["2026-12-15", None],
    )


# ---------------------------- response schemas ------------------------- #


class CohortSchema(BaseModel):
    """Cohort response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8",
                    "webinar_id": ("3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"),
                    "host_id": ("550e8400-e29b-41d4-a716-446655440000"),
                    "name": "Поток №3, осень 2026",
                    "max_participants": 30,
                    "starts_on": "2026-09-01",
                    "ends_on": "2026-12-15",
                    "enrollment_status": "open",
                    "lifecycle_status": "upcoming",
                    "created_at": "2026-04-29T10:00:00+00:00",
                },
            ],
        },
    )

    oid: UUID
    webinar_id: UUID
    host_id: UUID
    name: str | None
    max_participants: int | None
    starts_on: date
    ends_on: date | None
    enrollment_status: CohortEnrollmentStatus
    lifecycle_status: CohortLifecycleStatus
    created_at: datetime

    @classmethod
    def from_view(cls, view: CohortView) -> Self:
        return cls(
            oid=view.oid,
            webinar_id=view.webinar_id,
            host_id=view.host_id,
            name=view.name,
            max_participants=view.max_participants,
            starts_on=view.starts_on,
            ends_on=view.ends_on,
            enrollment_status=view.enrollment_status,
            lifecycle_status=view.lifecycle_status,
            created_at=view.created_at,
        )


# ------------------------------- routes -------------------------------- #


@router.get(
    "/{cohort_id}",
    summary="Get a single cohort (public)",
    operation_id="getCohortById",
    response_model=CohortSchema,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_one(
    interactor: FromDishka[GetCohortQueryHandler],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> CohortSchema:
    """Return a single cohort by id (public).

    Args:
        interactor: Injected get-cohort query handler.
        cohort_id: Target cohort's UUID, parsed from the URL path.

    Returns:
        :class:`CohortSchema` with full cohort metadata.

    Raises:
        EntityNotFoundError: No cohort with the given id; HTTP 404.
    """
    view = await interactor.run(GetCohortQuery(oid=CohortID(cohort_id)))
    return CohortSchema.from_view(view)


@router.patch(
    "/{cohort_id}/name",
    summary="Change a cohort's name",
    operation_id="updateCohortName",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_name(
    request: Request,
    payload: UpdateCohortNameSchema,
    interactor: FromDishka[UpdateCohortNameCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Replace (or clear) a cohort's display name.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": "<new name>" | null}``.
        interactor: Injected update-name command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Target cohort's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
        FieldError: ``CohortName`` VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCohortNameCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{cohort_id}/max-participants",
    summary="Change a cohort's participants cap",
    operation_id="updateCohortMaxParticipants",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_max_participants(
    request: Request,
    payload: UpdateCohortMaxParticipantsSchema,
    interactor: FromDishka[UpdateCohortMaxParticipantsCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Replace (or clear) the cohort's participants cap.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"value": <int> | null}``; `null` falls back to
            the webinar's ``default_max_participants``.
        interactor: Injected update-cap command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Target cohort's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
        FieldError: ``ParticipantsLimit`` VO violations; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateCohortMaxParticipantsCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
            value=payload.value,
        ),
    )


@router.patch(
    "/{cohort_id}/dates",
    summary="Reschedule a cohort's start and end dates",
    operation_id="rescheduleCohort",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def reschedule(
    request: Request,
    payload: RescheduleCohortSchema,
    interactor: FromDishka[RescheduleCohortCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Replace the cohort's start and end dates.

    Args:
        request: Source of the access-token cookie.
        payload: ``{"starts_on": "<date>", "ends_on": "<date>" | null}``.
        interactor: Injected reschedule command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Target cohort's UUID, parsed from the URL path.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RescheduleCohortCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
        ),
    )


@router.post(
    "/{cohort_id}/enrollment/open",
    summary="Open a cohort for new enrollments",
    operation_id="openCohortEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def open_enrollment(
    request: Request,
    interactor: FromDishka[OpenCohortEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``enrollment_status`` to ``OPEN``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        OpenCohortEnrollmentCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


@router.post(
    "/{cohort_id}/enrollment/close",
    summary="Close a cohort's enrollment",
    operation_id="closeCohortEnrollment",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def close_enrollment(
    request: Request,
    interactor: FromDishka[CloseCohortEnrollmentCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``enrollment_status`` to ``CLOSED``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CloseCohortEnrollmentCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


@router.post(
    "/{cohort_id}/enrollment/full",
    summary="Mark a cohort as full",
    operation_id="markCohortFull",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def mark_full(
    request: Request,
    interactor: FromDishka[MarkCohortFullCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``enrollment_status`` to ``FULL`` (manual override).

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        MarkCohortFullCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


@router.post(
    "/{cohort_id}/start",
    summary="Mark a cohort as active",
    operation_id="startCohort",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def start(
    request: Request,
    interactor: FromDishka[StartCohortCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``lifecycle_status`` to ``ACTIVE``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        StartCohortCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


@router.post(
    "/{cohort_id}/complete",
    summary="Mark a cohort as completed",
    operation_id="completeCohort",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete(
    request: Request,
    interactor: FromDishka[CompleteCohortCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``lifecycle_status`` to ``COMPLETED``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CompleteCohortCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


@router.post(
    "/{cohort_id}/cancel",
    summary="Cancel a cohort",
    operation_id="cancelCohort",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def cancel(
    request: Request,
    interactor: FromDishka[CancelCohortCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> None:
    """Set ``lifecycle_status`` to ``CANCELLED``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Cohort or its product missing; HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CancelCohortCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )


# ===================== Schedule + Session schemas ====================== #


class AddWebinarScheduleSchema(BaseModel):
    """Body for ``POST /cohorts/{cohort_id}/schedules``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "timezone": "Europe/Sofia",
                    "starts_on": "2026-09-01",
                    "ends_on": "2026-12-15",
                    "rrule": "FREQ=WEEKLY;BYDAY=FR;BYHOUR=19;BYMINUTE=0",
                    "duration_minutes": 90,
                },
            ],
        },
    )

    timezone: str = Field(
        max_length=IANA_TIMEZONE_MAX_LEN,
        description=(f"IANA timezone name. Max length {IANA_TIMEZONE_MAX_LEN}."),
        examples=["Europe/Sofia"],
    )
    starts_on: date = Field(
        description="Anchor date for ``DTSTART`` in the local timezone.",
        examples=["2026-09-01"],
    )
    ends_on: date | None = Field(
        default=None,
        description="Last permissible local date; `null` for open-ended.",
        examples=["2026-12-15", None],
    )
    rrule: str = Field(
        min_length=1,
        max_length=RRULE_MAX_LEN,
        description=(
            "RFC 5545 RRULE string. Validated server-side; invalid "
            "rules return HTTP 422 `InvalidRecurrenceRuleError`."
        ),
        examples=["FREQ=WEEKLY;BYDAY=FR;BYHOUR=19;BYMINUTE=0"],
    )
    duration_minutes: int = Field(
        ge=WEBINAR_DURATION_MINUTES_MIN,
        le=WEBINAR_DURATION_MINUTES_MAX,
        description=(
            "Per-session duration in minutes. Must be in "
            f"`[{WEBINAR_DURATION_MINUTES_MIN}, "
            f"{WEBINAR_DURATION_MINUTES_MAX}]`."
        ),
        examples=[90],
    )


class CreatedWebinarScheduleSchema(BaseModel):
    """Response for ``POST /cohorts/{cohort_id}/schedules``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "c3d2a91c-4e6b-49f1-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created schedule.",
        examples=["c3d2a91c-4e6b-49f1-9d11-9d4f0a44b6c8"],
    )


class WebinarScheduleListItemSchema(BaseModel):
    """Webinar schedule projection in ``GET /cohorts/{id}/schedules``."""

    oid: UUID
    cohort_id: UUID
    timezone: str
    starts_on: date
    ends_on: date | None
    rrule: str
    duration_minutes: int
    created_at: datetime

    @classmethod
    def from_view(cls, view: WebinarScheduleView) -> Self:
        return cls(
            oid=view.oid,
            cohort_id=view.cohort_id,
            timezone=view.timezone,
            starts_on=view.starts_on,
            ends_on=view.ends_on,
            rrule=view.rrule,
            duration_minutes=view.duration_minutes,
            created_at=view.created_at,
        )


class AddOneOffWebinarSessionSchema(BaseModel):
    """Body for ``POST /cohorts/{cohort_id}/sessions``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "starts_at": "2026-09-04T16:00:00+00:00",
                    "duration_minutes": 90,
                    "stream_url": "https://meet.example.com/oneoff",
                },
            ],
        },
    )

    starts_at: datetime = Field(
        description="Session start (UTC, timezone-aware).",
        examples=["2026-09-04T16:00:00+00:00"],
    )
    duration_minutes: int = Field(
        ge=WEBINAR_DURATION_MINUTES_MIN,
        le=WEBINAR_DURATION_MINUTES_MAX,
        description=(
            "Session duration in minutes. Must be in "
            f"`[{WEBINAR_DURATION_MINUTES_MIN}, "
            f"{WEBINAR_DURATION_MINUTES_MAX}]`."
        ),
        examples=[90],
    )
    stream_url: str | None = Field(
        default=None,
        max_length=SESSION_STREAM_URL_MAX_LEN,
        description=(
            "Optional per-session stream URL; `null` to fall back "
            "to the webinar's default. Must start with http(s):// "
            f"when set. Max length {SESSION_STREAM_URL_MAX_LEN} chars."
        ),
        examples=["https://meet.example.com/oneoff", None],
    )


class CreatedWebinarSessionSchema(BaseModel):
    """Response for ``POST /cohorts/{cohort_id}/sessions``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "a1b2c3d4-e5f6-7890-abcd-ef0123456789"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created session.",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef0123456789"],
    )


class WebinarSessionListItemSchema(BaseModel):
    """Webinar session projection in ``GET /cohorts/{id}/sessions``."""

    oid: UUID
    cohort_id: UUID
    schedule_id: UUID | None
    original_starts_at: datetime
    starts_at: datetime
    duration_minutes: int
    status: WebinarSessionStatus
    cancellation_reason: str | None
    stream_url: str | None
    recording_url: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: WebinarSessionView) -> Self:
        return cls(
            oid=view.oid,
            cohort_id=view.cohort_id,
            schedule_id=view.schedule_id,
            original_starts_at=view.original_starts_at,
            starts_at=view.starts_at,
            duration_minutes=view.duration_minutes,
            status=view.status,
            cancellation_reason=view.cancellation_reason,
            stream_url=view.stream_url,
            recording_url=view.recording_url,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


# ===================== Schedule + Session routes ======================= #


@router.post(
    "/{cohort_id}/schedules",
    summary="Create a recurring schedule under a cohort",
    operation_id="addWebinarSchedule",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedWebinarScheduleSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_schedule(
    request: Request,
    payload: AddWebinarScheduleSchema,
    interactor: FromDishka[AddWebinarScheduleCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> CreatedWebinarScheduleSchema:
    """Create a new schedule and enqueue materialization of its sessions.

    Args:
        request: Source of the access-token cookie.
        payload: Schedule fields validated by
            ``AddWebinarScheduleSchema``.
        interactor: Injected add-schedule command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Parent cohort UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the new schedule's UUID. Sessions are
        materialised asynchronously.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: No cohort with the given id; HTTP 404.
        FieldError: Schedule VO invariants violated (incl. semantic
            rrule check); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    schedule_id = await interactor.run(
        AddWebinarScheduleCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
            timezone=payload.timezone,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            rrule=payload.rrule,
            duration_minutes=payload.duration_minutes,
        ),
    )
    return CreatedWebinarScheduleSchema(oid=schedule_id)


@router.get(
    "/{cohort_id}/schedules",
    summary="List a cohort's schedules (public)",
    operation_id="getCohortSchedules",
    response_model=list[WebinarScheduleListItemSchema],
)
async def get_schedules(
    interactor: FromDishka[GetCohortSchedulesQueryHandler],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> list[WebinarScheduleListItemSchema]:
    """Return schedules attached to a cohort, by ascending start date.

    Args:
        interactor: Injected list-schedules query handler.
        cohort_id: Parent cohort UUID, parsed from the URL path.

    Returns:
        List of :class:`WebinarScheduleListItemSchema`.
    """
    views = await interactor.run(
        GetCohortSchedulesQuery(cohort_id=CohortID(cohort_id)),
    )
    return [WebinarScheduleListItemSchema.from_view(view) for view in views]


@router.post(
    "/{cohort_id}/sessions",
    summary="Create a one-off session under a cohort",
    operation_id="addOneOffWebinarSession",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedWebinarSessionSchema,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def add_one_off_session(
    request: Request,
    payload: AddOneOffWebinarSessionSchema,
    interactor: FromDishka[AddOneOffWebinarSessionCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> CreatedWebinarSessionSchema:
    """Create a manual session not derived from any schedule.

    Args:
        request: Source of the access-token cookie.
        payload: Session fields validated by
            ``AddOneOffWebinarSessionSchema``.
        interactor: Injected add-session command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Parent cohort UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the new session's UUID.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: No cohort with the given id; HTTP 404.
        FieldError: VO invariants violated; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    session_id = await interactor.run(
        AddOneOffWebinarSessionCommand(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
            starts_at=payload.starts_at,
            duration_minutes=payload.duration_minutes,
            stream_url=payload.stream_url,
        ),
    )
    return CreatedWebinarSessionSchema(oid=session_id)


@router.get(
    "/{cohort_id}/sessions",
    summary="List a cohort's sessions (public)",
    operation_id="getCohortSessions",
    response_model=list[WebinarSessionListItemSchema],
)
async def get_sessions(
    interactor: FromDishka[GetCohortSessionsQueryHandler],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> list[WebinarSessionListItemSchema]:
    """Return sessions attached to a cohort, by ascending start time.

    Args:
        interactor: Injected list-sessions query handler.
        cohort_id: Parent cohort UUID, parsed from the URL path.

    Returns:
        List of :class:`WebinarSessionListItemSchema`.
    """
    views = await interactor.run(
        GetCohortSessionsQuery(cohort_id=CohortID(cohort_id)),
    )
    return [WebinarSessionListItemSchema.from_view(view) for view in views]


# ========================= Enrollment schemas ========================== #


class CreatedWebinarEnrollmentSchema(BaseModel):
    """Response for ``POST /cohorts/{cohort_id}/enrollments``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"oid": "d4e5f607-1a23-4d2c-9d11-9d4f0a44b6c8"},
            ],
        },
    )

    oid: UUID = Field(
        description="UUID of the freshly created enrollment.",
        examples=["d4e5f607-1a23-4d2c-9d11-9d4f0a44b6c8"],
    )


# ========================= Enrollment routes =========================== #


@router.post(
    "/{cohort_id}/enrollments",
    summary="Enroll the current user into a cohort",
    operation_id="enrollIntoCohort",
    status_code=status.HTTP_201_CREATED,
    dependencies=_AUTH_SECURITY,
    response_model=CreatedWebinarEnrollmentSchema,
    error_map=AUTHENTICATED_WITH_FIELD_MAP
    | {
        EnrollmentClosedError: ENROLLMENT_CLOSED_RULE,
        AlreadyEnrolledError: ALREADY_ENROLLED_RULE,
        CohortFullError: COHORT_FULL_RULE,
    },
)
async def enroll(
    request: Request,
    interactor: FromDishka[EnrollStudentInCohortCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> CreatedWebinarEnrollmentSchema:
    """Self-enroll the current user into a cohort.

    Pre-conditions enforced server-side:

    * ``cohort.enrollment_status == open`` — else
      HTTP 409 ``EnrollmentClosed``.
    * No existing enrollment of the same student in the cohort —
      else HTTP 409 ``AlreadyEnrolled``.
    * ``cohort.max_participants`` not reached — else HTTP 409
      ``CohortFull`` (and the cohort is auto-flipped to ``full``).

    Args:
        request: Source of the access-token cookie.
        interactor: Injected enroll command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Target cohort UUID, parsed from the URL path.

    Returns:
        ``201 Created`` with the new enrollment's UUID.

    Raises:
        InvalidTokenError: HTTP 401.
        EntityNotFoundError: HTTP 404.
        EnrollmentClosedError: HTTP 409.
        AlreadyEnrolledError: HTTP 409.
        CohortFullError: HTTP 409.
    """
    ctx = await auth.authenticate(request)
    enrollment_id = await interactor.run(
        EnrollStudentInCohortCommand(
            student_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )
    return CreatedWebinarEnrollmentSchema(oid=enrollment_id)


@router.get(
    "/{cohort_id}/enrollments",
    summary="List a cohort's enrollments (host/author only)",
    operation_id="getCohortEnrollments",
    response_model=list[EnrollmentSchema],
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def get_enrollments(
    request: Request,
    interactor: FromDishka[GetCohortEnrollmentsQueryHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,
) -> list[EnrollmentSchema]:
    """Return cohort enrollments. Caller must be host or product author.

    Returns the unified :class:`EnrollmentSchema`; ``type`` is
    always ``"webinar"`` for this endpoint.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    views = await interactor.run(
        GetCohortEnrollmentsQuery(
            actor_id=ctx.user_id,
            cohort_id=CohortID(cohort_id),
        ),
    )
    return [EnrollmentSchema.from_view(v) for v in views]
