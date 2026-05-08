import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.cohort.ids import CohortID
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID


@dataclass
class WebinarEnrollment(BaseEntity[WebinarEnrollmentID]):
    """A student's enrollment in a specific webinar cohort.

    Standalone aggregate root. Uniqueness ``(cohort_id,
    student_id)`` is enforced at the DB level — a student cannot
    be enrolled twice into the same cohort. ``CASCADE`` on cohort
    deletion (the enrollment dies with its cohort);
    ``RESTRICT`` on student deletion (history kept, must be
    handled before the user can be removed).
    """

    cohort_id: CohortID
    student_id: UserID
    status: WebinarEnrollmentStatus
    enrolled_at: datetime

    def drop(self) -> None:
        self.status = WebinarEnrollmentStatus.DROPPED

    def complete(self) -> None:
        self.status = WebinarEnrollmentStatus.COMPLETED

    def refund(self) -> None:
        self.status = WebinarEnrollmentStatus.REFUNDED

    @classmethod
    def create(
        cls,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> Self:
        return cls(
            oid=WebinarEnrollmentID(uuid.uuid4()),
            cohort_id=cohort_id,
            student_id=student_id,
            status=WebinarEnrollmentStatus.ACTIVE,
            enrolled_at=datetime.now(timezone.utc),
        )
