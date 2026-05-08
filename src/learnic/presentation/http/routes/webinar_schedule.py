from datetime import date, datetime
from typing import Final, Self
from uuid import UUID

from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, Path, Request, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.commands.webinar_schedule.delete import (
    DeleteWebinarScheduleCommand,
    DeleteWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.update import (
    UpdateWebinarScheduleCommand,
    UpdateWebinarScheduleCommandHandler,
)
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleView,
)
from learnic.entities.cohort.constants import (
    IANA_TIMEZONE_MAX_LEN,
    RRULE_MAX_LEN,
)
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.product.constants import (
    WEBINAR_DURATION_MINUTES_MAX,
    WEBINAR_DURATION_MINUTES_MIN,
)
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import (
    AUTHENTICATED_OWNER_FIELD_MAP,
)
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/cohorts/{cohort_id}/schedules",
    tags=["WebinarSchedules"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]
_COHORT_ID_PATH: Final = Path(
    description="Parent cohort UUID.",
    examples=["8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8"],
)
_SCHEDULE_ID_PATH: Final = Path(
    description="Target webinar schedule UUID.",
    examples=["c3d2a91c-4e6b-49f1-9d11-9d4f0a44b6c8"],
)


class UpdateWebinarScheduleSchema(BaseModel):
    """Body for ``PUT /cohorts/{cohort_id}/schedules/{schedule_id}``.

    PUT semantics — every field is required. Update kicks off a
    re-materialization task that adds new sessions according to the
    updated rule, starting after the last already-materialised
    session (existing sessions are not retroactively rewritten).
    """

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
        description=(
            "IANA timezone name (e.g. `Europe/Sofia`). "
            f"Max length {IANA_TIMEZONE_MAX_LEN}."
        ),
        examples=["Europe/Sofia"],
    )
    starts_on: date = Field(
        description="Anchor date for ``DTSTART`` in the local timezone.",
        examples=["2026-09-01"],
    )
    ends_on: date | None = Field(
        description=("Last permissible local date; `null` for open-ended rules."),
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


class WebinarScheduleSchema(BaseModel):
    """Webinar schedule response projection."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "oid": "c3d2a91c-4e6b-49f1-9d11-9d4f0a44b6c8",
                    "cohort_id": "8b5e9f12-4a31-4d2c-9d11-9d4f0a44b6c8",
                    "timezone": "Europe/Sofia",
                    "starts_on": "2026-09-01",
                    "ends_on": "2026-12-15",
                    "rrule": "FREQ=WEEKLY;BYDAY=FR;BYHOUR=19;BYMINUTE=0",
                    "duration_minutes": 90,
                    "created_at": "2026-04-29T10:00:00+00:00",
                },
            ],
        },
    )

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


@router.put(
    "/{schedule_id}",
    summary="Replace a webinar schedule and re-materialize",
    operation_id="updateWebinarSchedule",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def update_schedule(
    request: Request,
    payload: UpdateWebinarScheduleSchema,
    interactor: FromDishka[UpdateWebinarScheduleCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    schedule_id: UUID = _SCHEDULE_ID_PATH,
) -> None:
    """Replace all schedule fields and enqueue a re-materialization task.

    Args:
        request: Source of the access-token cookie.
        payload: Full schedule fields validated by
            ``UpdateWebinarScheduleSchema``.
        interactor: Injected update command handler.
        auth: Injected authenticator that validates the access cookie.
        cohort_id: Parent cohort UUID, parsed from the URL path.
        schedule_id: Target schedule UUID, parsed from the URL path.

    Returns:
        ``204 No Content``. The materialization task runs
        asynchronously; new sessions appear shortly after.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Schedule or its parent cohort missing;
            HTTP 404.
        FieldError: Schedule VO invariants violated (incl. semantic
            rrule check); HTTP 422.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        UpdateWebinarScheduleCommand(
            actor_id=ctx.user_id,
            schedule_id=WebinarScheduleID(schedule_id),
            timezone=payload.timezone,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            rrule=payload.rrule,
            duration_minutes=payload.duration_minutes,
        ),
    )


@router.delete(
    "/{schedule_id}",
    summary="Delete a webinar schedule",
    operation_id="deleteWebinarSchedule",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_AUTH_SECURITY,
    error_map=AUTHENTICATED_OWNER_FIELD_MAP,
)
async def delete_schedule(
    request: Request,
    interactor: FromDishka[DeleteWebinarScheduleCommandHandler],
    auth: FromDishka[Authenticator],
    cohort_id: UUID = _COHORT_ID_PATH,  # noqa: ARG001
    schedule_id: UUID = _SCHEDULE_ID_PATH,
) -> None:
    """Delete the schedule. Existing sessions become orphan (FK SET NULL).

    Returns:
        ``204 No Content``.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        NotResourceOwnerError: Caller is neither host nor product
            author; HTTP 403.
        EntityNotFoundError: Schedule or its parent cohort missing;
            HTTP 404.
    """
    ctx = await auth.authenticate(request)
    await interactor.run(
        DeleteWebinarScheduleCommand(
            actor_id=ctx.user_id,
            schedule_id=WebinarScheduleID(schedule_id),
        ),
    )
