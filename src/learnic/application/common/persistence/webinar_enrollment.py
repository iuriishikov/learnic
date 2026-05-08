from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.cohort.ids import CohortID
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID
from learnic.entities.webinar_enrollment.models import WebinarEnrollment


@dataclass(slots=True, frozen=True)
class WebinarEnrollmentView:
    """Read-side projection of :class:`WebinarEnrollment`."""

    oid: WebinarEnrollmentID
    cohort_id: CohortID
    student_id: UserID
    status: WebinarEnrollmentStatus
    enrolled_at: datetime


class WebinarEnrollmentGateway(Protocol):
    """Write-side lookups for :class:`WebinarEnrollment`."""

    async def with_id(
        self,
        oid: WebinarEnrollmentID,
    ) -> WebinarEnrollment | None: ...

    async def with_cohort_and_student(
        self,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> WebinarEnrollment | None: ...

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarEnrollment]: ...


class WebinarEnrollmentReader(Protocol):
    """Read-side queries returning :class:`WebinarEnrollmentView`."""

    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarEnrollmentView]: ...

    async def for_student(
        self,
        student_id: UserID,
    ) -> list[WebinarEnrollmentView]: ...
