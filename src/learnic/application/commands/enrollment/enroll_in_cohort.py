from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    WebinarEnrollmentTarget,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class EnrollStudentInCohortCommand:
    student_id: UserID
    cohort_id: CohortID


@final
class EnrollStudentInCohortCommandHandler:
    """Self-enroll the current student into a webinar cohort.

    Thin wrapper: builds a :class:`WebinarEnrollmentTarget` from
    the HTTP command and delegates to :class:`EnrollmentService`.
    All type-specific work (cohort status / capacity, post-insert
    flip to ``FULL``) lives in :class:`WebinarEnrollmentStrategy`.
    """

    def __init__(self, service: EnrollmentService) -> None:
        self._service: Final = service

    async def run(
        self,
        data: EnrollStudentInCohortCommand,
    ) -> EnrollmentID:
        return await self._service.enroll(
            student_id=data.student_id,
            target=WebinarEnrollmentTarget(cohort_id=data.cohort_id),
        )
