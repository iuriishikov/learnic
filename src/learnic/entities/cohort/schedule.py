import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Self

from learnic.entities.cohort.ids import CohortID, WebinarScheduleID
from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.value_objects import WebinarSessionDuration


@dataclass
class WebinarSchedule(BaseEntity[WebinarScheduleID]):
    """Recurrence rule attached to a :class:`Cohort`.

    Child entity of the Cohort aggregate (CASCADE on parent
    delete). A cohort may have several schedules over its
    lifetime — when the timetable changes, a new schedule
    supersedes the previous one rather than being mutated in
    place.
    """

    cohort_id: CohortID
    timezone: IanaTimezone
    starts_on: date
    rrule: RecurrenceRule
    duration_minutes: WebinarSessionDuration
    created_at: datetime
    ends_on: date | None = None

    def change_rrule(self, new_rrule: RecurrenceRule) -> None:
        self.rrule = new_rrule

    def change_timezone(self, new_timezone: IanaTimezone) -> None:
        self.timezone = new_timezone

    def change_duration(
        self,
        new_duration: WebinarSessionDuration,
    ) -> None:
        self.duration_minutes = new_duration

    def change_dates(
        self,
        starts_on: date,
        ends_on: date | None,
    ) -> None:
        self.starts_on = starts_on
        self.ends_on = ends_on

    @classmethod
    def create(
        cls,
        cohort_id: CohortID,
        tz: IanaTimezone,
        starts_on: date,
        rrule: RecurrenceRule,
        duration_minutes: WebinarSessionDuration,
        ends_on: date | None = None,
    ) -> Self:
        return cls(
            oid=WebinarScheduleID(uuid.uuid4()),
            cohort_id=cohort_id,
            timezone=tz,
            starts_on=starts_on,
            rrule=rrule,
            duration_minutes=duration_minutes,
            created_at=datetime.now(timezone.utc),
            ends_on=ends_on,
        )
