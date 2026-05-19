from typing import ClassVar, Final, final

from typing_extensions import override

from learnic.application.common.enrollment.strategies import (
    EnrollmentStrategy,
    EnrollmentTarget,
    WebinarEnrollmentTarget,
)
from learnic.application.common.errors import (
    CohortFullError,
    EnrollmentClosedError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.transaction import EntitySaver
from learnic.entities.cohort.enums import CohortEnrollmentStatus
from learnic.entities.enrollment.enums import EnrollmentType
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.user.models import UserID


@final
class WebinarEnrollmentStrategy(EnrollmentStrategy):
    """Concrete strategy for ``EnrollmentType.WEBINAR``.

    Pre-conditions:

    * Cohort exists.
    * ``cohort.enrollment_status == OPEN`` — closed cohorts and
      full cohorts both reject new enrollments.
    * Cohort cap (if set) not yet hit.

    Side effect: when the new enrollment hits the cap exactly,
    flips ``cohort.enrollment_status → FULL`` so subsequent
    attempts get :class:`EnrollmentClosedError`. The mutation
    is picked up by the unit-of-work and persisted in the same
    commit as the new enrollment.
    """

    enrollment_type: ClassVar[EnrollmentType] = EnrollmentType.WEBINAR

    def __init__(
        self,
        entity_saver: EntitySaver,
        cohort_gateway: CohortGateway,
        enrollment_gateway: EnrollmentGateway,
    ) -> None:
        self._entity_saver: Final = entity_saver
        self._cohort_gateway: Final = cohort_gateway
        self._enrollment_gateway: Final = enrollment_gateway

    @override
    async def find_existing(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment | None:
        assert isinstance(target, WebinarEnrollmentTarget)  # noqa: S101
        return await self._enrollment_gateway.with_cohort_and_student(
            target.cohort_id,
            student_id,
        )

    @override
    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment:
        assert isinstance(target, WebinarEnrollmentTarget)  # noqa: S101
        cohort = await self._cohort_gateway.with_id(target.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(target.cohort_id)
        if cohort.enrollment_status is not CohortEnrollmentStatus.OPEN:
            raise EnrollmentClosedError(
                target.cohort_id,
                cohort.enrollment_status.value,
            )
        if cohort.max_participants is not None:
            current = await self._enrollment_gateway.for_cohort(
                target.cohort_id,
            )
            if len(current) >= cohort.max_participants.value:
                cohort.mark_full()
                raise CohortFullError(target.cohort_id)

        enrollment = Enrollment.create_webinar(
            student_id=student_id,
            cohort_id=target.cohort_id,
        )
        assert enrollment.webinar_details is not None  # noqa: S101
        self._entity_saver.add_one(enrollment)
        self._entity_saver.add_one(enrollment.webinar_details)

        # Re-check capacity post-insert — flip to FULL if THIS row
        # is the one that hit the cap exactly. Both the new row and
        # the cohort mutation get persisted in the same commit.
        if cohort.max_participants is not None:
            current_count = (
                len(
                    await self._enrollment_gateway.for_cohort(
                        target.cohort_id,
                    ),
                )
                + 1
            )
            if current_count >= cohort.max_participants.value:
                cohort.mark_full()

        return enrollment
