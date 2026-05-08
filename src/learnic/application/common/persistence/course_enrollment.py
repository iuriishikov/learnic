from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CourseEnrollmentView:
    """Read-side projection of :class:`CourseEnrollment`."""

    oid: CourseEnrollmentID
    product_id: ProductID
    student_id: UserID
    release_id: CourseReleaseID | None
    status: CourseEnrollmentStatus
    progress_percent: int
    enrolled_at: datetime
    completed_at: datetime | None


class CourseEnrollmentGateway(Protocol):
    """Write-side lookups for :class:`CourseEnrollment`."""

    async def with_id(
        self,
        oid: CourseEnrollmentID,
    ) -> CourseEnrollment | None: ...

    async def with_product_and_student(
        self,
        product_id: ProductID,
        student_id: UserID,
    ) -> CourseEnrollment | None: ...

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseEnrollment]: ...


class CourseEnrollmentReader(Protocol):
    """Read-side queries returning :class:`CourseEnrollmentView`."""

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseEnrollmentView]: ...

    async def for_student(
        self,
        student_id: UserID,
    ) -> list[CourseEnrollmentView]: ...
