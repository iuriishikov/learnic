from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RefundCourseEnrollmentCommand:
    actor_id: UserID
    enrollment_id: CourseEnrollmentID


@final
class RefundCourseEnrollmentCommandHandler:
    """Marks a course enrollment refunded (product author only)."""

    def __init__(
        self,
        transaction: Transaction,
        enrollment_gateway: CourseEnrollmentGateway,
        product_gateway: ProductGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._enrollment_gateway: Final = enrollment_gateway
        self._product_gateway: Final = product_gateway

    async def run(self, data: RefundCourseEnrollmentCommand) -> None:
        enrollment = await self._enrollment_gateway.with_id(
            data.enrollment_id,
        )
        if enrollment is None:
            raise EntityNotFoundError(data.enrollment_id)
        product = await self._product_gateway.with_id(
            enrollment.product_id,
        )
        if product is None:
            raise EntityNotFoundError(enrollment.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(
                data.enrollment_id,
                data.actor_id,
            )
        enrollment.refund()
        await self._transaction.commit()
