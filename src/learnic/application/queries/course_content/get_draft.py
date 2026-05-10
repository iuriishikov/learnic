from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    NotACourseError,
)
from learnic.application.common.persistence.course_content import (
    CourseContentReader,
    CourseDraftView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetCourseDraftQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetCourseDraftQueryHandler:
    """Return the full draft tree of a course.

    Caller needs ``READ_PRODUCT`` on the target product, so the
    owner and any collaborator with that permission can read the
    draft structure (modules, lessons, blocks).
    """

    def __init__(
        self,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        content_reader: CourseContentReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._content_reader: Final = content_reader

    async def run(self, data: GetCourseDraftQuery) -> CourseDraftView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        if product.type is not ProductType.COURSE:
            raise NotACourseError(data.product_id)
        return await self._content_reader.get_draft(data.product_id)
