from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotACourseError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseReader,
    CourseReleaseSummaryView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListCourseReleasesQuery:
    actor_id: UserID
    product_id: ProductID


@final
class ListCourseReleasesQueryHandler:
    """Return all releases of a course, newest first. Author-only."""

    def __init__(
        self,
        product_gateway: ProductGateway,
        release_reader: CourseReleaseReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: ListCourseReleasesQuery,
    ) -> list[CourseReleaseSummaryView]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        if product.type is not ProductType.COURSE:
            raise NotACourseError(data.product_id)
        return await self._release_reader.list_for_product(data.product_id)
