import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.cohort.ids import CohortID
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.capabilities import (
    ENROLLMENT_TYPE_CAPABILITIES,
    EnrollmentCapability,
)
from learnic.entities.enrollment.constants import (
    PROGRESS_PERCENT_MAX,
)
from learnic.entities.enrollment.course_details import CourseDetails
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.errors import (
    EnrollmentDoesNotSupportError,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.enrollment.webinar_details import WebinarDetails
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass
class Enrollment(BaseEntity[EnrollmentID]):
    """A student's enrollment in a learning product.

    Two flavours unified by ``type``:

    * ``COURSE`` — asynchronous, pinned to a specific course
      release at signup, tracks a self-reported progress percent.
      The course-specific data (``product_id``, ``release_id``,
      ``progress``, ``completed_at``) lives in
      :class:`CourseDetails`.
    * ``WEBINAR`` — synchronous, attached to a cohort with its
      own schedule. The webinar-specific data (``cohort_id``)
      lives in :class:`WebinarDetails`.

    Following the ``Product`` / ``WebinarDetails`` pattern, the
    side-detail entity is **loaded out-of-band by the gateway**
    after the main row is fetched (composition split, no ORM
    relationship). The class-level ``= None`` defaults keep the
    fields readable on freshly hydrated instances; SQLAlchemy
    ignores them during load.

    Statuses are shared (``ACTIVE | COMPLETED | REFUNDED``). The
    historical webinar-specific ``DROPPED`` was retired — see
    ``EnrollmentStatus`` for the migration story.
    """

    type: EnrollmentType
    student_id: UserID
    status: EnrollmentStatus
    enrolled_at: datetime
    course_details: CourseDetails | None = None
    webinar_details: WebinarDetails | None = None

    def supports(self, capability: EnrollmentCapability) -> bool:
        return capability in ENROLLMENT_TYPE_CAPABILITIES[self.type]

    def require_supports(self, capability: EnrollmentCapability) -> None:
        """Raise :class:`EnrollmentDoesNotSupportError` if missing.

        Mirrors :meth:`Product.require_supports`. Keeps capability
        gating in one place instead of scattering ``if type !=`` in
        every handler.
        """
        if not self.supports(capability):
            raise EnrollmentDoesNotSupportError(
                enrollment_id=self.oid,
                enrollment_type=self.type.value,
                capability=capability.value,
            )

    def update_progress(self, new_progress: ProgressPercent) -> None:
        """Course-only. Updates ``course_details.progress`` in place.

        Reaching :data:`PROGRESS_PERCENT_MAX` does NOT auto-complete
        — the application layer's handler is responsible for the
        transition, mirroring the previous
        ``update_course_progress`` flow.
        """
        self.require_supports(EnrollmentCapability.HAS_PROGRESS)
        assert self.course_details is not None  # noqa: S101
        self.course_details.progress = new_progress

    def complete(self) -> None:
        """Mark this enrollment completed.

        For courses, also pins ``progress`` to 100 % and stamps
        ``completed_at`` so the read-side projection mirrors the
        previous ``CourseEnrollment.complete()`` shape. For
        webinars the completion timestamp lives only on the
        parent (``Enrollment`` carries no separate completion
        field beyond ``status``).
        """
        self.status = EnrollmentStatus.COMPLETED
        if self.course_details is not None:
            self.course_details.progress = ProgressPercent(
                PROGRESS_PERCENT_MAX,
            )
            self.course_details.completed_at = datetime.now(timezone.utc)

    def refund(self) -> None:
        self.status = EnrollmentStatus.REFUNDED

    @classmethod
    def create_course(
        cls,
        *,
        student_id: UserID,
        product_id: ProductID,
        release_id: CourseReleaseID,
    ) -> Self:
        oid = EnrollmentID(uuid.uuid4())
        return cls(
            oid=oid,
            type=EnrollmentType.COURSE,
            student_id=student_id,
            status=EnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
            course_details=CourseDetails.create(
                enrollment_id=oid,
                product_id=product_id,
                student_id=student_id,
                release_id=release_id,
                progress=ProgressPercent(0),
            ),
            webinar_details=None,
        )

    @classmethod
    def create_webinar(
        cls,
        *,
        student_id: UserID,
        cohort_id: CohortID,
    ) -> Self:
        oid = EnrollmentID(uuid.uuid4())
        return cls(
            oid=oid,
            type=EnrollmentType.WEBINAR,
            student_id=student_id,
            status=EnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
            course_details=None,
            webinar_details=WebinarDetails.create(
                enrollment_id=oid,
                cohort_id=cohort_id,
                student_id=student_id,
            ),
        )
