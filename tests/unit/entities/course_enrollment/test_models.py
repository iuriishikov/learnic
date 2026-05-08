import uuid

from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.course_enrollment.value_objects import (
    ProgressPercent,
)
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


def _enrollment() -> CourseEnrollment:
    return CourseEnrollment.create(
        product_id=ProductID(uuid.uuid4()),
        student_id=UserID(uuid.uuid4()),
        release_id=CourseReleaseID(uuid.uuid4()),
    )


class TestCourseEnrollment:
    def test_initial_state(self) -> None:
        e = _enrollment()
        assert e.status is CourseEnrollmentStatus.ACTIVE
        assert e.progress.value == 0
        assert e.completed_at is None

    def test_update_progress(self) -> None:
        e = _enrollment()
        e.update_progress(ProgressPercent(50))
        assert e.progress.value == 50
        assert e.status is CourseEnrollmentStatus.ACTIVE

    def test_complete_sets_progress_100_and_timestamp(self) -> None:
        e = _enrollment()
        e.complete()
        assert e.progress.value == 100
        assert e.status is CourseEnrollmentStatus.COMPLETED
        assert e.completed_at is not None

    def test_refund(self) -> None:
        e = _enrollment()
        e.refund()
        assert e.status is CourseEnrollmentStatus.REFUNDED
