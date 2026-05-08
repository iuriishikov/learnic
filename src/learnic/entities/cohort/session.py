import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.cohort.enums import WebinarSessionStatus
from learnic.entities.cohort.ids import (
    CohortID,
    WebinarScheduleID,
    WebinarSessionID,
)
from learnic.entities.cohort.value_objects import (
    CancellationReason,
    RecordingUrl,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.value_objects import (
    StreamUrl,
    WebinarSessionDuration,
)


@dataclass
class WebinarSession(BaseEntity[WebinarSessionID]):
    """A single materialised session of a webinar cohort.

    Standalone aggregate root — sessions have independent lifecycles
    (rescheduled, cancelled, completed) and there can be many per
    cohort, so loading them through the Cohort aggregate would be
    wasteful. Linked to ``Cohort`` (CASCADE) and optionally to a
    ``WebinarSchedule`` it was generated from (SET NULL — schedule
    deletions don't erase historical sessions).

    The pair ``(schedule_id, original_starts_at)`` is unique at
    the DB level — guards against double-materialisation when an
    rrule is expanded into concrete sessions.
    """

    cohort_id: CohortID
    original_starts_at: datetime
    starts_at: datetime
    duration_minutes: WebinarSessionDuration
    status: WebinarSessionStatus
    created_at: datetime
    updated_at: datetime
    schedule_id: WebinarScheduleID | None = None
    cancellation_reason: CancellationReason | None = None
    stream_url: StreamUrl | None = None
    recording_url: RecordingUrl | None = None

    def reschedule(self, new_starts_at: datetime) -> None:
        self.starts_at = new_starts_at
        self.status = WebinarSessionStatus.RESCHEDULED

    def cancel(self, reason: CancellationReason | None = None) -> None:
        self.status = WebinarSessionStatus.CANCELLED
        if reason is not None:
            self.cancellation_reason = reason

    def complete(self) -> None:
        self.status = WebinarSessionStatus.COMPLETED

    def attach_recording(self, url: RecordingUrl) -> None:
        self.recording_url = url

    def remove_recording(self) -> None:
        self.recording_url = None

    def change_stream_url(self, url: StreamUrl | None) -> None:
        self.stream_url = url

    def change_duration(
        self,
        new_duration: WebinarSessionDuration,
    ) -> None:
        self.duration_minutes = new_duration

    @classmethod
    def create(
        cls,
        cohort_id: CohortID,
        original_starts_at: datetime,
        duration_minutes: WebinarSessionDuration,
        schedule_id: WebinarScheduleID | None = None,
        stream_url: StreamUrl | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=WebinarSessionID(uuid.uuid4()),
            cohort_id=cohort_id,
            schedule_id=schedule_id,
            original_starts_at=original_starts_at,
            starts_at=original_starts_at,
            duration_minutes=duration_minutes,
            status=WebinarSessionStatus.SCHEDULED,
            cancellation_reason=None,
            stream_url=stream_url,
            recording_url=None,
            created_at=now,
            updated_at=now,
        )
