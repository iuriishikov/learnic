from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CohortFullError,
    EnrollmentClosedError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentGateway,
)
from learnic.entities.cohort.enums import CohortEnrollmentStatus
from learnic.entities.cohort.ids import CohortID
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID
from learnic.entities.webinar_enrollment.models import WebinarEnrollment


@dataclass(slots=True, frozen=True)
class EnrollStudentInCohortCommand:
    student_id: UserID
    cohort_id: CohortID


@final
class EnrollStudentInCohortCommandHandler:
    """Records the current user as enrolled in a cohort.

    Pre-conditions:
        * The cohort exists and ``enrollment_status == OPEN``.
        * The student has no existing enrollment in the same cohort.
        * If ``cohort.max_participants`` is set, current
          enrollment count is below the cap.

    On reaching the cap exactly, this command flips the cohort's
    ``enrollment_status`` to ``FULL`` so subsequent attempts get
    :class:`EnrollmentClosedError`.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        cohort_gateway: CohortGateway,
        enrollment_gateway: WebinarEnrollmentGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._cohort_gateway: Final = cohort_gateway
        self._enrollment_gateway: Final = enrollment_gateway

    async def run(
        self,
        data: EnrollStudentInCohortCommand,
    ) -> WebinarEnrollmentID:
        cohort = await self._cohort_gateway.with_id(data.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(data.cohort_id)
        if cohort.enrollment_status is not CohortEnrollmentStatus.OPEN:
            raise EnrollmentClosedError(
                data.cohort_id,
                cohort.enrollment_status.value,
            )
        existing = await self._enrollment_gateway.with_cohort_and_student(
            data.cohort_id,
            data.student_id,
        )
        if existing is not None:
            raise AlreadyEnrolledError(
                data.cohort_id,
                data.student_id,
            )
        if cohort.max_participants is not None:
            current = await self._enrollment_gateway.for_cohort(
                data.cohort_id,
            )
            if len(current) >= cohort.max_participants.value:
                cohort.mark_full()
                raise CohortFullError(data.cohort_id)
        enrollment = WebinarEnrollment.create(
            cohort_id=data.cohort_id,
            student_id=data.student_id,
        )
        self._entity_saver.add_one(enrollment)
        # Flip to FULL after this insert if we hit the cap exactly.
        if cohort.max_participants is not None:
            current_count = (
                len(
                    await self._enrollment_gateway.for_cohort(data.cohort_id),
                )
                + 1
            )
            if current_count >= cohort.max_participants.value:
                cohort.mark_full()
        await self._transaction.commit()
        return enrollment.oid
