from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.cohort.ids import CohortID
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CourseDetailsView:
    """Read-side projection of :class:`CourseDetails`."""

    product_id: ProductID
    release_id: CourseReleaseID | None
    progress_percent: int
    completed_at: datetime | None


@dataclass(slots=True, frozen=True)
class WebinarDetailsView:
    """Read-side projection of :class:`WebinarDetails`.

    Distinct from ``product.WebinarDetailsView`` (Product side
    holds webinar *defaults*, this side holds the *enrollment's*
    cohort reference) — different shapes, different consumers, so
    they live in different modules.
    """

    cohort_id: CohortID


@dataclass(slots=True, frozen=True)
class EnrollmentView:
    """Unified read-side projection of :class:`Enrollment`.

    Exactly one of ``course_details`` / ``webinar_details`` is set,
    matching ``type``. Readers populate both via the same joined
    query so SPAs do not need a follow-up call.
    """

    oid: EnrollmentID
    type: EnrollmentType
    student_id: UserID
    status: EnrollmentStatus
    enrolled_at: datetime
    course_details: CourseDetailsView | None
    webinar_details: WebinarDetailsView | None


class EnrollmentGateway(Protocol):
    """Write-side lookups for :class:`Enrollment`.

    ``with_id`` returns a fully-hydrated aggregate including
    ``course_details`` / ``webinar_details`` loaded out-of-band
    from the matching side-detail table (composition split, same
    pattern as :class:`ProductGateway`).
    """

    async def with_id(self, oid: EnrollmentID) -> Enrollment | None: ...

    async def with_product_and_student(
        self,
        product_id: ProductID,
        student_id: UserID,
    ) -> Enrollment | None: ...

    async def with_cohort_and_student(
        self,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> Enrollment | None: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[Enrollment]: ...


class EnrollmentReader(Protocol):
    """Read-side queries returning :class:`EnrollmentView`."""

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[EnrollmentView]: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[EnrollmentView]: ...

    async def for_student(
        self,
        student_id: UserID,
    ) -> list[EnrollmentView]:
        """Return all enrollments for a student across both types.

        Replaces the previous ``CourseEnrollmentReader.for_student``
        and ``WebinarEnrollmentReader.for_student`` — clients that
        only care about one type filter on
        :class:`EnrollmentView.type`.
        """
        ...
