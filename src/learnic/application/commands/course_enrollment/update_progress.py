from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_enrollment.constants import (
    PROGRESS_PERCENT_MAX,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.course_enrollment.value_objects import (
    ProgressPercent,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateCourseProgressCommand:
    actor_id: UserID
    enrollment_id: CourseEnrollmentID
    progress_percent: int


@final
class UpdateCourseProgressCommandHandler:
    """Updates a student's own progress on a course.

    Authorisation: only the student themselves may update progress
    on their enrollment. Reaching ``100`` automatically transitions
    the enrollment to ``COMPLETED`` (logic lives in the entity's
    ``complete()`` method).
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: CourseEnrollmentGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway

    async def run(self, data: UpdateCourseProgressCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        if enrollment.student_id != data.actor_id:
            raise NotResourceOwnerError(
                data.enrollment_id,
                data.actor_id,
            )
        progress = ProgressPercent(data.progress_percent)
        if progress.value >= PROGRESS_PERCENT_MAX:
            enrollment.complete()
        else:
            enrollment.update_progress(progress)
        await self._transaction.commit()
