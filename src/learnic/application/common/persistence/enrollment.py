from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.enums import (
    EnrollmentKind,
    EnrollmentStatus,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CourseEnrollmentDetailsView:
    """Read-side projection of :class:`CourseEnrollmentDetails`."""

    release_id: CourseReleaseID | None
    progress_percent: int
    completed_at: datetime | None


@dataclass(slots=True, frozen=True)
class EnrollmentView:
    """Unified read-side projection of :class:`Enrollment`."""

    oid: EnrollmentID
    kind: EnrollmentKind
    product_id: ProductID
    student_id: UserID
    status: EnrollmentStatus
    enrolled_at: datetime
    details: CourseEnrollmentDetailsView | None


class EnrollmentGateway(Protocol):
    """Write-side lookups and inserts for :class:`Enrollment`."""

    async def add(self, enrollment: Enrollment) -> None:
        """Insert ``enrollment`` and its kind-specific subtype row.

        Mirrors :class:`NotificationGateway.add` — the gateway
        owns the cross-table insert because the polymorphic
        ``details`` body is not mapped imperatively.
        """
        ...

    async def with_id(self, oid: EnrollmentID) -> Enrollment | None: ...

    async def with_product_and_student(
        self,
        product_id: ProductID,
        student_id: UserID,
    ) -> Enrollment | None: ...

    async def update_course_details(self, enrollment: Enrollment) -> None:
        """Persist the course-kind ``details`` body of ``enrollment``.

        The polymorphic ``details`` body is not mapped
        imperatively, so SQLAlchemy cannot auto-flush mutations
        on it. Handlers that mutate ``details`` (e.g. re-pinning
        the release) call this method to write the subtype row.
        """
        ...


class EnrollmentReader(Protocol):
    """Read-side queries returning :class:`EnrollmentView`."""

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[EnrollmentView]: ...

    async def for_student(
        self,
        student_id: UserID,
    ) -> list[EnrollmentView]:
        """Return all enrollments for a student."""
        ...
