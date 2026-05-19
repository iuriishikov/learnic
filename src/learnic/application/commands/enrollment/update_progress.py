from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.capabilities import EnrollmentCapability
from learnic.entities.enrollment.constants import (
    PROGRESS_PERCENT_MAX,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateProgressCommand:
    actor_id: UserID
    enrollment_id: EnrollmentID
    progress_percent: int


@final
class UpdateProgressCommandHandler:
    """Updates a student's self-reported progress on a course enrollment.

    Course-only — the entity raises
    :class:`EnrollmentDoesNotSupportError` via
    :meth:`Enrollment.require_supports` for kinds that lack
    ``HAS_PROGRESS``.

    Authorisation: only the student themselves may update.
    Reaching :data:`PROGRESS_PERCENT_MAX` auto-marks the
    enrollment completed (sets ``details.completed_at``) but
    does NOT change ``status`` — a completed enrollment is
    still ACTIVE.
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: EnrollmentGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway

    async def run(self, data: UpdateProgressCommand) -> None:
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
        enrollment.require_supports(EnrollmentCapability.HAS_PROGRESS)
        progress = ProgressPercent(data.progress_percent)
        if progress.value >= PROGRESS_PERCENT_MAX:
            enrollment.mark_completed()
        else:
            enrollment.update_progress(progress)
        await self._transaction.commit()
