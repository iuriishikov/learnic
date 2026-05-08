import uuid

from learnic.entities.cohort.ids import CohortID
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.models import WebinarEnrollment


def _enrollment() -> WebinarEnrollment:
    return WebinarEnrollment.create(
        cohort_id=CohortID(uuid.uuid4()),
        student_id=UserID(uuid.uuid4()),
    )


class TestWebinarEnrollment:
    def test_initial_state(self) -> None:
        e = _enrollment()
        assert e.status is WebinarEnrollmentStatus.ACTIVE

    def test_drop(self) -> None:
        e = _enrollment()
        e.drop()
        assert e.status is WebinarEnrollmentStatus.DROPPED

    def test_complete(self) -> None:
        e = _enrollment()
        e.complete()
        assert e.status is WebinarEnrollmentStatus.COMPLETED

    def test_refund(self) -> None:
        e = _enrollment()
        e.refund()
        assert e.status is WebinarEnrollmentStatus.REFUNDED
