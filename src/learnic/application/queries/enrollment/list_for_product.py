from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentReader,
    EnrollmentView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetProductEnrollmentsQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetProductEnrollmentsQueryHandler:
    """List course-type enrollments of a product.

    Caller needs ``READ_PRODUCT`` on the target product so owner
    and collaborators with that permission can see students.
    Only course enrollments — webinar enrollments are listed per
    cohort via :class:`GetCohortEnrollmentsQueryHandler`.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: EnrollmentReader,
        product_gateway: ProductGateway,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader
        self._product_gateway: Final = product_gateway

    async def run(
        self,
        data: GetProductEnrollmentsQuery,
    ) -> list[EnrollmentView]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        return await self._reader.for_product(data.product_id)
