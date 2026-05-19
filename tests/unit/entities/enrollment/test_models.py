import uuid

import pytest

from learnic.entities.cohort.ids import CohortID
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.capabilities import EnrollmentCapability
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.errors import (
    EnrollmentDoesNotSupportError,
)
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


def _course_enrollment() -> Enrollment:
    return Enrollment.create_course(
        student_id=UserID(uuid.uuid4()),
        product_id=ProductID(uuid.uuid4()),
        release_id=CourseReleaseID(uuid.uuid4()),
    )


def _webinar_enrollment() -> Enrollment:
    return Enrollment.create_webinar(
        student_id=UserID(uuid.uuid4()),
        cohort_id=CohortID(uuid.uuid4()),
    )


class TestCourseEnrollment:
    def test_initial_state(self) -> None:
        e = _course_enrollment()
        assert e.type is EnrollmentType.COURSE
        assert e.status is EnrollmentStatus.ACTIVE
        assert e.course_details is not None
        assert e.course_details.progress.value == 0
        assert e.course_details.completed_at is None
        assert e.webinar_details is None

    def test_details_share_parent_oid_and_student(self) -> None:
        e = _course_enrollment()
        assert e.course_details is not None
        assert e.course_details.oid == e.oid
        assert e.course_details.student_id == e.student_id

    def test_update_progress(self) -> None:
        e = _course_enrollment()
        e.update_progress(ProgressPercent(50))
        assert e.course_details is not None
        assert e.course_details.progress.value == 50
        assert e.status is EnrollmentStatus.ACTIVE

    def test_complete_sets_progress_100_and_timestamp(self) -> None:
        e = _course_enrollment()
        e.complete()
        assert e.status is EnrollmentStatus.COMPLETED
        assert e.course_details is not None
        assert e.course_details.progress.value == 100
        assert e.course_details.completed_at is not None

    def test_refund(self) -> None:
        e = _course_enrollment()
        e.refund()
        assert e.status is EnrollmentStatus.REFUNDED


class TestWebinarEnrollment:
    def test_initial_state(self) -> None:
        e = _webinar_enrollment()
        assert e.type is EnrollmentType.WEBINAR
        assert e.status is EnrollmentStatus.ACTIVE
        assert e.webinar_details is not None
        assert e.course_details is None

    def test_complete(self) -> None:
        e = _webinar_enrollment()
        e.complete()
        assert e.status is EnrollmentStatus.COMPLETED

    def test_refund(self) -> None:
        e = _webinar_enrollment()
        e.refund()
        assert e.status is EnrollmentStatus.REFUNDED

    def test_update_progress_raises_capability_error(self) -> None:
        e = _webinar_enrollment()
        with pytest.raises(EnrollmentDoesNotSupportError) as exc:
            e.update_progress(ProgressPercent(50))
        assert exc.value.capability == (
            EnrollmentCapability.HAS_PROGRESS.value
        )
        assert exc.value.enrollment_type == EnrollmentType.WEBINAR.value
