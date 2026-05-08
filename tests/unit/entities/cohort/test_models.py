import uuid
from datetime import date, datetime, timezone

from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
    WebinarSessionStatus,
)
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.cohort.value_objects import (
    CancellationReason,
    CohortName,
    IanaTimezone,
    RecordingUrl,
    RecurrenceRule,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import (
    ParticipantsLimit,
    StreamUrl,
    WebinarSessionDuration,
)
from learnic.entities.user.models import UserID


def _cohort() -> Cohort:
    return Cohort.create(
        webinar_id=ProductID(uuid.uuid4()),
        host_id=UserID(uuid.uuid4()),
        starts_on=date(2026, 9, 1),
    )


class TestCreateCohort:
    def test_initial_state(self) -> None:
        c = _cohort()
        assert c.enrollment_status is CohortEnrollmentStatus.OPEN
        assert c.lifecycle_status is CohortLifecycleStatus.UPCOMING
        assert c.name is None
        assert c.max_participants is None
        assert c.ends_on is None


class TestCohortMutators:
    def test_rename(self) -> None:
        c = _cohort()
        c.rename(CohortName("Поток №3"))
        assert c.name is not None
        assert c.name.value == "Поток №3"

    def test_clear_name(self) -> None:
        c = _cohort()
        c.rename(CohortName("X"))
        c.rename(None)
        assert c.name is None

    def test_change_max_participants(self) -> None:
        c = _cohort()
        c.change_max_participants(ParticipantsLimit(50))
        assert c.max_participants is not None
        assert c.max_participants.value == 50

    def test_enrollment_transitions(self) -> None:
        c = _cohort()
        c.close_enrollment()
        assert c.enrollment_status is CohortEnrollmentStatus.CLOSED
        c.mark_full()
        assert c.enrollment_status is CohortEnrollmentStatus.FULL
        c.open_enrollment()
        assert c.enrollment_status is CohortEnrollmentStatus.OPEN

    def test_lifecycle_transitions(self) -> None:
        c = _cohort()
        c.start()
        assert c.lifecycle_status is CohortLifecycleStatus.ACTIVE
        c.complete()
        assert c.lifecycle_status is CohortLifecycleStatus.COMPLETED
        c.cancel()
        assert c.lifecycle_status is CohortLifecycleStatus.CANCELLED


class TestWebinarSchedule:
    def test_create(self) -> None:
        c = _cohort()
        s = WebinarSchedule.create(
            cohort_id=c.oid,
            tz=IanaTimezone("Europe/Sofia"),
            starts_on=date(2026, 9, 1),
            rrule=RecurrenceRule("FREQ=WEEKLY;BYDAY=FR"),
            duration_minutes=WebinarSessionDuration(90),
        )
        assert s.cohort_id == c.oid
        assert s.timezone.value == "Europe/Sofia"
        assert s.ends_on is None


class TestWebinarSession:
    def test_create_initial_state(self) -> None:
        c = _cohort()
        starts_at = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)
        s = WebinarSession.create(
            cohort_id=c.oid,
            original_starts_at=starts_at,
            duration_minutes=WebinarSessionDuration(90),
        )
        assert s.status is WebinarSessionStatus.SCHEDULED
        assert s.starts_at == starts_at
        assert s.original_starts_at == starts_at
        assert s.schedule_id is None
        assert s.cancellation_reason is None
        assert s.recording_url is None

    def test_reschedule_changes_status(self) -> None:
        c = _cohort()
        s = WebinarSession.create(
            cohort_id=c.oid,
            original_starts_at=datetime(
                2026,
                9,
                4,
                16,
                0,
                tzinfo=timezone.utc,
            ),
            duration_minutes=WebinarSessionDuration(90),
        )
        new_start = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)
        s.reschedule(new_start)
        assert s.starts_at == new_start
        assert s.status is WebinarSessionStatus.RESCHEDULED

    def test_cancel_with_reason(self) -> None:
        c = _cohort()
        s = WebinarSession.create(
            cohort_id=c.oid,
            original_starts_at=datetime(
                2026,
                9,
                4,
                16,
                0,
                tzinfo=timezone.utc,
            ),
            duration_minutes=WebinarSessionDuration(90),
        )
        s.cancel(CancellationReason("Host illness"))
        assert s.status is WebinarSessionStatus.CANCELLED
        assert s.cancellation_reason is not None
        assert s.cancellation_reason.value == "Host illness"

    def test_attach_and_remove_recording(self) -> None:
        c = _cohort()
        s = WebinarSession.create(
            cohort_id=c.oid,
            original_starts_at=datetime(
                2026,
                9,
                4,
                16,
                0,
                tzinfo=timezone.utc,
            ),
            duration_minutes=WebinarSessionDuration(90),
        )
        s.attach_recording(RecordingUrl("https://x.example/rec.mp4"))
        assert s.recording_url is not None
        s.remove_recording()
        assert s.recording_url is None

    def test_change_stream_url(self) -> None:
        c = _cohort()
        s = WebinarSession.create(
            cohort_id=c.oid,
            original_starts_at=datetime(
                2026,
                9,
                4,
                16,
                0,
                tzinfo=timezone.utc,
            ),
            duration_minutes=WebinarSessionDuration(90),
        )
        s.change_stream_url(StreamUrl("https://meet.example/x"))
        assert s.stream_url is not None
        s.change_stream_url(None)
        assert s.stream_url is None
