from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.enums import EnrollmentType
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RefundEnrollmentCommand:
    actor_id: UserID
    enrollment_id: EnrollmentID


@final
class RefundEnrollmentCommandHandler:
    """Flip an enrollment to ``REFUNDED`` (course or webinar).

    Status-only — payment-processor integration is left to a
    future ``PaymentRefundService`` Protocol. Mirrors the
    authorisation split of :class:`CompleteEnrollmentCommandHandler`.
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: EnrollmentGateway,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: RefundEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        if enrollment.type is EnrollmentType.COURSE:
            assert enrollment.course_details is not None  # noqa: S101
            await self._authorizer.require(
                data.actor_id,
                AuthzTarget.for_product(
                    enrollment.course_details.product_id,
                ),
                Permission.MANAGE_RELEASES,
            )
        else:
            assert enrollment.webinar_details is not None  # noqa: S101
            cohort = await self._cohort_gateway.with_id(
                enrollment.webinar_details.cohort_id,
            )
            if cohort is None:
                raise EntityNotFoundError(
                    enrollment.webinar_details.cohort_id,
                )
            await assert_cohort_authorized(
                cohort,
                data.actor_id,
                self._authorizer,
            )
        enrollment.refund()
        await self._transaction.commit()
