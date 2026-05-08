from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentReader,
    CourseEnrollmentView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetProductCourseEnrollmentsQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetProductCourseEnrollmentsQueryHandler:
    """Lists enrollments of a course product — author only."""

    def __init__(
        self,
        reader: CourseEnrollmentReader,
        product_gateway: ProductGateway,
    ) -> None:
        self._reader: Final = reader
        self._product_gateway: Final = product_gateway

    async def run(
        self,
        data: GetProductCourseEnrollmentsQuery,
    ) -> list[CourseEnrollmentView]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(
                data.product_id,
                data.actor_id,
            )
        return await self._reader.for_product(data.product_id)
