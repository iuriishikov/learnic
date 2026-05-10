from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
    CourseReleaseGateway,
    CourseReleaseReader,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetCourseReleaseContentQuery:
    actor_id: UserID
    product_id: ProductID
    release_id: CourseReleaseID


@final
class GetCourseReleaseContentQueryHandler:
    """Return the full content tree of a specific release.

    Caller needs ``READ_PRODUCT`` on the target product. Verifies
    that ``release_id`` actually belongs to ``product_id`` so an
    arbitrary release can't be peeked at by guessing UUIDs.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        release_gateway: CourseReleaseGateway,
        release_reader: CourseReleaseReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._release_gateway: Final = release_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: GetCourseReleaseContentQuery,
    ) -> CourseReleaseContentView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        release = await self._release_gateway.with_id(data.release_id)
        if release is None or release.product_id != data.product_id:
            raise EntityNotFoundError(data.release_id)
        view = await self._release_reader.get_content(data.release_id)
        if view is None:
            raise EntityNotFoundError(data.release_id)
        return view
