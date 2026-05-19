import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.capabilities import (
    ENROLLMENT_KIND_CAPABILITIES,
    EnrollmentCapability,
)
from learnic.entities.enrollment.constants import (
    PROGRESS_PERCENT_MAX,
)
from learnic.entities.enrollment.details import (
    CourseEnrollmentDetails,
    EnrollmentDetails,
)
from learnic.entities.enrollment.enums import (
    EnrollmentKind,
    EnrollmentStatus,
)
from learnic.entities.enrollment.errors import (
    EnrollmentDoesNotSupportError,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass
class Enrollment(BaseEntity[EnrollmentID]):
    """A student's enrollment in a learning product.

    Polymorphic on :attr:`kind`. The kind-specific body lives in
    :attr:`details`, a subclass of :class:`EnrollmentDetails`
    mapped to a kind-specific subtype table — same pattern as
    :class:`Notification` + :class:`NotificationDetails`.

    ``product_id`` lives on the base row so the
    ``UNIQUE(product_id, student_id)`` constraint sits directly
    on the enrollments table (Postgres unique constraints span
    one table only). With ``product_id`` on the base, the details
    subtype tables no longer need to denormalise it.
    """

    product_id: ProductID
    student_id: UserID
    kind: EnrollmentKind
    status: EnrollmentStatus
    enrolled_at: datetime
    details: EnrollmentDetails = field(default_factory=EnrollmentDetails)

    def supports(self, capability: EnrollmentCapability) -> bool:
        return capability in ENROLLMENT_KIND_CAPABILITIES[self.kind]

    def require_supports(self, capability: EnrollmentCapability) -> None:
        """Raise :class:`EnrollmentDoesNotSupportError` if missing."""
        if not self.supports(capability):
            raise EnrollmentDoesNotSupportError(
                enrollment_id=self.oid,
                enrollment_kind=self.kind.value,
                capability=capability.value,
            )

    def update_progress(self, new_progress: ProgressPercent) -> None:
        """Course-only. Updates ``details.progress`` in place."""
        self.require_supports(EnrollmentCapability.HAS_PROGRESS)
        assert isinstance(self.details, CourseEnrollmentDetails)  # noqa: S101
        self.details.progress = new_progress

    def mark_completed(self) -> None:
        """Mark course completion. Does NOT change status.

        Completion lives on details (``completed_at``), orthogonal
        to access state (``status``). A completed enrollment is
        still ACTIVE; only revocation moves status off ACTIVE.
        """
        self.require_supports(EnrollmentCapability.HAS_PROGRESS)
        assert isinstance(self.details, CourseEnrollmentDetails)  # noqa: S101
        self.details.progress = ProgressPercent(PROGRESS_PERCENT_MAX)
        self.details.completed_at = datetime.now(timezone.utc)

    def revoke(self) -> None:
        """Revoke this enrollment (author/admin action)."""
        self.status = EnrollmentStatus.REVOKED

    @classmethod
    def create_course(
        cls,
        *,
        student_id: UserID,
        product_id: ProductID,
        release_id: CourseReleaseID,
    ) -> Self:
        return cls(
            oid=EnrollmentID(uuid.uuid4()),
            product_id=product_id,
            student_id=student_id,
            kind=EnrollmentKind.COURSE,
            status=EnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
            details=CourseEnrollmentDetails(
                release_id=release_id,
                progress=ProgressPercent(0),
                completed_at=None,
            ),
        )
