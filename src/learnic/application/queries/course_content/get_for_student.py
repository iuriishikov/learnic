from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
    CourseReleaseReader,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyCourseContentQuery:
    actor_id: UserID
    product_id: ProductID


@final
class GetMyCourseContentQueryHandler:
    """Return the pinned-release content for an enrolled student.

    Resolution order:
        1. Product exists and is a course → otherwise 404 (we
           don't leak existence of webinar products under the
           course-content endpoint).
        2. The current user has an enrollment for the product
           that is not REFUNDED. Refunded enrollments are
           treated as "no access" — content is hidden as if the
           enrollment never existed (still 404, no separate 403
           to avoid telegraphing past payment status).
        3. The enrollment's pinned release exists.

    Returns the snapshot tree of the **enrollment's** release
    (strict pinning) — not the latest release of the course.
    """

    def __init__(
        self,
        product_gateway: ProductGateway,
        enrollment_gateway: CourseEnrollmentGateway,
        release_reader: CourseReleaseReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: GetMyCourseContentQuery,
    ) -> CourseReleaseContentView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None or product.type is not ProductType.COURSE:
            raise EntityNotFoundError(data.product_id)

        enrollment = await self._enrollment_gateway.with_product_and_student(
            data.product_id,
            data.actor_id,
        )
        if enrollment is None or enrollment.status is CourseEnrollmentStatus.REFUNDED:
            raise EntityNotFoundError(data.product_id)

        view = await self._release_reader.get_content(enrollment.release_id)
        if view is None:
            # Enrollment row exists but the pinned release is
            # missing — invariant violation; surface as 404 so
            # the client retries / contacts support.
            raise EntityNotFoundError(enrollment.release_id)
        return view
