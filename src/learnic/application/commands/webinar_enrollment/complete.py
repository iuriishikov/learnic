from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentGateway,
)
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID


@dataclass(slots=True, frozen=True)
class CompleteWebinarEnrollmentCommand:
    actor_id: UserID
    enrollment_id: WebinarEnrollmentID


@final
class CompleteWebinarEnrollmentCommandHandler:
    """Marks a single enrollment as completed (host/author only)."""

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: WebinarEnrollmentGateway,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: CompleteWebinarEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        cohort = await self._cohort_gateway.with_id(
            enrollment.cohort_id,
        )
        if cohort is None:
            raise EntityNotFoundError(enrollment.cohort_id)
        await assert_cohort_authorized(
            cohort,
            data.actor_id,
            self._authorizer,
        )
        enrollment.complete()
        await self._transaction.commit()
