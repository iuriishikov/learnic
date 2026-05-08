from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from learnic.entities.cohort.ids import CohortID, WebinarScheduleID
from learnic.entities.cohort.schedule import WebinarSchedule


@dataclass(slots=True, frozen=True)
class WebinarScheduleView:
    """Read-side projection of :class:`WebinarSchedule`."""

    oid: WebinarScheduleID
    cohort_id: CohortID
    timezone: str
    starts_on: date
    ends_on: date | None
    rrule: str
    duration_minutes: int
    created_at: datetime


class WebinarScheduleGateway(Protocol):
    """Write-side lookups for :class:`WebinarSchedule`."""

    async def with_id(
        self,
        oid: WebinarScheduleID,
    ) -> WebinarSchedule | None: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSchedule]: ...

    async def delete(self, schedule: WebinarSchedule) -> None: ...


class WebinarScheduleReader(Protocol):
    """Read-side queries returning :class:`WebinarScheduleView`."""

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarScheduleView]: ...
