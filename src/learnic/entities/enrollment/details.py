from dataclasses import dataclass
from datetime import datetime

from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.value_objects import ProgressPercent


@dataclass
class EnrollmentDetails:
    """Polymorphic body for an :class:`Enrollment`.

    The base class is empty — each enrollment kind defines a
    concrete subclass with kind-specific fields. Same pattern as
    :class:`NotificationDetails`.
    """


@dataclass
class CourseEnrollmentDetails(EnrollmentDetails):
    """Course-kind specific data for an :class:`Enrollment`.

    Lives in the ``enrollment_course_details`` subtype table,
    loaded out-of-band by the gateway after the parent row.
    """

    release_id: CourseReleaseID
    progress: ProgressPercent
    completed_at: datetime | None = None
