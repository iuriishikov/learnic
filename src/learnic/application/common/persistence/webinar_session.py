from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.cohort.enums import WebinarSessionStatus
from learnic.entities.cohort.ids import (
    CohortID,
    WebinarScheduleID,
    WebinarSessionID,
)
from learnic.entities.cohort.session import WebinarSession


@dataclass(slots=True, frozen=True)
class WebinarSessionView:
    """Read-side projection of :class:`WebinarSession`."""

    oid: WebinarSessionID
    cohort_id: CohortID
    schedule_id: WebinarScheduleID | None
    original_starts_at: datetime
    starts_at: datetime
    duration_minutes: int
    status: WebinarSessionStatus
    cancellation_reason: str | None
    stream_url: str | None
    recording_url: str | None
    created_at: datetime
    updated_at: datetime


class WebinarSessionGateway(Protocol):
    """Write-side lookups for :class:`WebinarSession`."""

    async def with_id(
        self,
        oid: WebinarSessionID,
    ) -> WebinarSession | None: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSession]: ...

    async def last_original_starts_at(
        self,
        schedule_id: WebinarScheduleID,
    ) -> datetime | None:
        """Return the largest ``original_starts_at`` for ``schedule_id``.

        Used by the materialization task as a cursor — the worker
        only generates sessions strictly after this timestamp.
        ``None`` when no sessions exist yet for the schedule.
        """
        ...

    async def delete(self, session: WebinarSession) -> None: ...


class WebinarSessionReader(Protocol):
    """Read-side queries returning :class:`WebinarSessionView`."""

    async def with_id(
        self,
        oid: WebinarSessionID,
    ) -> WebinarSessionView | None: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSessionView]: ...
