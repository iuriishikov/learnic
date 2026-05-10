from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentReader,
    CourseEnrollmentView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetProductCourseEnrollmentsQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetProductCourseEnrollmentsQueryHandler:
    """Lists enrollments of a course product.

    Caller needs ``READ_PRODUCT`` on the target product, so the
    owner and any collaborator with that permission can see who
    is enrolled.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: CourseEnrollmentReader,
        product_gateway: ProductGateway,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader
        self._product_gateway: Final = product_gateway

    async def run(
        self,
        data: GetProductCourseEnrollmentsQuery,
    ) -> list[CourseEnrollmentView]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        return await self._reader.for_product(data.product_id)
