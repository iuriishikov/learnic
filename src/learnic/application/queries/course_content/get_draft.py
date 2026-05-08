from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotACourseError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_content import (
    CourseContentReader,
    CourseDraftView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetCourseDraftQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetCourseDraftQueryHandler:
    """Return the full draft tree of a course. Author-only access."""

    def __init__(
        self,
        product_gateway: ProductGateway,
        content_reader: CourseContentReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._content_reader: Final = content_reader

    async def run(self, data: GetCourseDraftQuery) -> CourseDraftView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        if product.type is not ProductType.COURSE:
            raise NotACourseError(data.product_id)
        return await self._content_reader.get_draft(data.product_id)
