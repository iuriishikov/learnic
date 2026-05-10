from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CompleteCourseEnrollmentCommand:
    actor_id: UserID
    enrollment_id: CourseEnrollmentID


@final
class CompleteCourseEnrollmentCommandHandler:
    """Marks a course enrollment completed.

    The student themselves drives completion implicitly by hitting
    100 % via :class:`UpdateCourseProgressCommand`; this command is
    the explicit override available to anyone with
    ``MANAGE_RELEASES`` on the parent product (owner included).
    """

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: CourseEnrollmentGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: CompleteCourseEnrollmentCommand) -> None:
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
        enrollment.complete()
        await self._transaction.commit()
