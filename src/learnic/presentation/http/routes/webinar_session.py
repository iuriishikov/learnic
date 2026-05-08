from datetime import datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.webinar_session.attach_recording import (
    AttachWebinarSessionRecordingCommand,
    AttachWebinarSessionRecordingCommandHandler,
)
from learnic.application.commands.webinar_session.cancel import (
    CancelWebinarSessionCommand,
    CancelWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.change_stream_url import (
    ChangeWebinarSessionStreamUrlCommand,
    ChangeWebinarSessionStreamUrlCommandHandler,
)
from learnic.application.commands.webinar_session.complete import (
    CompleteWebinarSessionCommand,
    CompleteWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.remove_recording import (
    RemoveWebinarSessionRecordingCommand,
    RemoveWebinarSessionRecordingCommandHandler,
)
from learnic.application.commands.webinar_session.reschedule import (
    RescheduleWebinarSessionCommand,
    RescheduleWebinarSessionCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.webinar_session import (
    WebinarSessionView,
)
from learnic.application.queries.webinar_session.get import (
    GetWebinarSessionQuery,
    GetWebinarSessionQueryHandler,
)
from learnic.entities.cohort.constants import (
    CANCELLATION_REASON_MAX_LEN,
    RECORDING_URL_MAX_LEN,
    SESSION_STREAM_URL_MAX_LEN,
)
from learnic.entities.cohort.enums import WebinarSessionStatus
from learnic.entities.cohort.ids import WebinarSessionID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/cohorts/{cohort_id}/sessions",
    tags=["WebinarSessions"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COHORT_ID_PATH: Final = Path(
    description="Parent cohort UUID.",
    examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
)
_SESSION_ID_PATH: Final = Path(
    description="Target webinar session UUID.",
    examples=["a1b2c3d4-e5f6-7890-abcd-ef0123456789"],
)


# ---------------------------- request schemas -------------------------- #


class RescheduleWebinarSessionSchema(BaseModel):
    """Body for ``PATCH /cohorts/{cohort_id}/sessions/{session_id}/starts-at``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"starts_at": "2026-09-08T16:00:00+00:00"}],
        },
    )

    starts_at: datetime = Field(
        description=(
            "New session start (UTC, timezone-aware). Status flips to ``rescheduled``."
        ),
        examples=["2026-09-08T16:00:00+00:00"],
    )


class CancelWebinarSessionSchema(BaseModel):
    """Body for ``POST /cohorts/{cohort_id}/sessions/{session_id}/cancel``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"reason": "Host illness"}, {"reason": None}],
        },
    )

    reason: str | None = Field(
        max_length=CANCELLATION_REASON_MAX_LEN,
        description=(
            "Optional cancellation reason. "
            f"Max length {CANCELLATION_REASON_MAX_LEN} chars."
        ),
        examples=["Host illness", None],
    )


class AttachRecordingSchema(BaseModel):
    """Body for ``PUT /cohorts/{cohort_id}/sessions/{session_id}/recording``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "url": ("https://recordings.example.com/2026-09-04.mp4"),
                },
            ],
        },
    )

    url: str = Field(
        min_length=1,
        max_length=RECORDING_URL_MAX_LEN,
        description=(
            "Recording URL (must start with http(s)://). "
            f"Max length {RECORDING_URL_MAX_LEN} chars."
        ),
        examples=["https://recordings.example.com/2026-09-04.mp4"],
    )


class ChangeStreamUrlSchema(BaseModel):
    """Body for ``PATCH /cohorts/{cohort_id}/sessions/{session_id}/stream-url``."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"url": "https://meet.example.com/sql-2"},
                {"url": None},
            ],
        },
    )

    url: str | None = Field(
        max_length=SESSION_STREAM_URL_MAX_LEN,
        description=(
            "Per-session streaming URL, or `null` to fall back to "
            "the webinar's default. Must start with http(s):// "
            f"when set. Max length {SESSION_STREAM_URL_MAX_LEN} chars."
        ),
        examples=["https://meet.example.com/sql-2", None],
    )


# ---------------------------- response schema -------------------------- #


class WebinarSessionSchema(BaseModel):
    """Webinar session response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
                    "cohort_id": ("8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"),
                    "schedule_id": ("c3d2a91c-4e6b-49f1-9d11-9d4f0a44b6c8"),
                    "original_starts_at": "2026-09-04T16:00:00+00:00",
                    "starts_at": "2026-09-04T16:00:00+00:00",
                    "duration_minutes": 90,
                    "status": "scheduled",
                    "cancellation_reason": None,
                    "stream_url": None,
                    "recording_url": None,
                    "created_at": "2026-04-29T10:00:00+00:00",
                    "updated_at": "2026-04-29T10:00:00+00:00",
                },
            ],
        },
    )

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


# ------------------------------- routes -------------------------------- #


@router.get(
    "/{session_id}",
    summary="Get a single webinar session (public)",
    operation_id="getWebinarSessionById",
    response_model=WebinarSessionSchema,
    error_map={EntityNotFoundError: ENTITY_NOT_FOUND_RULE},
)
async def get_one(
    interactor: FromDishka[GetWebinarSessionQueryHandler],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> WebinarSessionSchema:
    """Return a single webinar session by id (public).

    Raises:
        EntityNotFoundError: No session with the given id; HTTP 404.
    """
    view = await interactor.run(
        GetWebinarSessionQuery(oid=WebinarSessionID(session_id)),
    )
    return WebinarSessionSchema.from_view(view)


@router.patch(
    "/{session_id}/starts-at",
    summary="Reschedule a webinar session",
    operation_id="rescheduleWebinarSession",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def reschedule_session(
    request: Request,
    payload: RescheduleWebinarSessionSchema,
    interactor: FromDishka[RescheduleWebinarSessionCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Set a new ``starts_at`` and flip ``status`` to ``rescheduled``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RescheduleWebinarSessionCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
            starts_at=payload.starts_at,
        ),
    )


@router.post(
    "/{session_id}/cancel",
    summary="Cancel a webinar session",
    operation_id="cancelWebinarSession",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def cancel_session(
    request: Request,
    payload: CancelWebinarSessionSchema,
    interactor: FromDishka[CancelWebinarSessionCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Set ``status`` to ``cancelled`` (with optional reason).

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: ``CancellationReason`` VO invariants; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CancelWebinarSessionCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
            reason=payload.reason,
        ),
    )


@router.post(
    "/{session_id}/complete",
    summary="Mark a webinar session as completed",
    operation_id="completeWebinarSession",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def complete_session(
    request: Request,
    interactor: FromDishka[CompleteWebinarSessionCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Set ``status`` to ``completed``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        CompleteWebinarSessionCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
        ),
    )


@router.put(
    "/{session_id}/recording",
    summary="Attach a recording URL to a webinar session",
    operation_id="attachWebinarSessionRecording",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def attach_recording(
    request: Request,
    payload: AttachRecordingSchema,
    interactor: FromDishka[AttachWebinarSessionRecordingCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Set ``recording_url``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: ``RecordingUrl`` VO invariants; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        AttachWebinarSessionRecordingCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
            url=payload.url,
        ),
    )


@router.delete(
    "/{session_id}/recording",
    summary="Detach a recording URL from a webinar session",
    operation_id="removeWebinarSessionRecording",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def remove_recording(
    request: Request,
    interactor: FromDishka[RemoveWebinarSessionRecordingCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Clear ``recording_url``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        RemoveWebinarSessionRecordingCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
        ),
    )


@router.patch(
    "/{session_id}/stream-url",
    summary="Replace (or clear) a webinar session's stream URL",
    operation_id="changeWebinarSessionStreamUrl",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def change_stream_url(
    request: Request,
    payload: ChangeStreamUrlSchema,
    interactor: FromDishka[ChangeWebinarSessionStreamUrlCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    session_id: UUID = _SESSION_ID_PATH,
) -> None:
    """Update or clear ``stream_url``.

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: HTTP 401.
        NotResourceOwnerError: HTTP 403.
        EntityNotFoundError: HTTP 404.
        FieldError: ``StreamUrl`` VO invariants; HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        ChangeWebinarSessionStreamUrlCommand(
            actor_id=ctx.user_id,
            session_id=WebinarSessionID(session_id),
            url=payload.url,
        ),
    )
