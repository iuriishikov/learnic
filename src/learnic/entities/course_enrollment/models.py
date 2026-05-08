import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.course_enrollment.value_objects import (
    ProgressPercent,
)
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass
class CourseEnrollment(BaseEntity[CourseEnrollmentID]):
    """A student's enrollment in a self-paced course product.

    Standalone aggregate root. Uniqueness ``(product_id,
    student_id)`` is enforced at the DB level — a student cannot
    be enrolled twice into the same course. ``CASCADE`` on product
    deletion; ``RESTRICT`` on student deletion (history kept).

    Captures ``release_id`` at enrollment time — the student is
    pinned to whatever release was current at signup. Strict
    pinning: students keep that version forever (no opt-in upgrade
    in this phase). Refund-policy semantics around future
    ``major`` releases will read this column.

    Unlike :class:`WebinarEnrollment`, course enrollments track
    asynchronous progress via :class:`ProgressPercent`; there is
    no ``DROPPED`` status (drop-out manifests as a refund or as a
    stalled-but-active enrollment).
    """

    product_id: ProductID
    student_id: UserID
    release_id: CourseReleaseID
    status: CourseEnrollmentStatus
    progress: ProgressPercent
    enrolled_at: datetime
    completed_at: datetime | None = None

    def update_progress(self, new_progress: ProgressPercent) -> None:
        self.progress = new_progress

    def complete(self) -> None:
        self.status = CourseEnrollmentStatus.COMPLETED
        self.progress = ProgressPercent(PROGRESS_PERCENT_MAX)
        self.completed_at = datetime.now(timezone.utc)

    def refund(self) -> None:
        self.status = CourseEnrollmentStatus.REFUNDED

    @classmethod
    def create(
        cls,
        product_id: ProductID,
        student_id: UserID,
        release_id: CourseReleaseID,
    ) -> Self:
        return cls(
            oid=CourseEnrollmentID(uuid.uuid4()),
            product_id=product_id,
            student_id=student_id,
            release_id=release_id,
            status=CourseEnrollmentStatus.ACTIVE,
            progress=ProgressPercent(PROGRESS_PERCENT_MIN),
            enrolled_at=datetime.now(timezone.utc),
            completed_at=None,
        )
