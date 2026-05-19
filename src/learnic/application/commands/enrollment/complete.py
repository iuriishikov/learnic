from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CompleteEnrollmentCommand:
    actor_id: UserID
    enrollment_id: EnrollmentID


@final
class CompleteEnrollmentCommandHandler:
    """Mark an enrollment completed.

    Caller needs ``MANAGE_RELEASES`` on the parent product (owner
    short-circuits inside the authorizer). Completion lives on
    ``details.completed_at`` — it does NOT change the enrollment
    ``status`` (a completed enrollment is still ACTIVE; only
    revocation moves status off ACTIVE).
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: EnrollmentGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: CompleteEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(enrollment.product_id),
            Permission.MANAGE_RELEASES,
        )
        enrollment.mark_completed()
        await self._transaction.commit()
