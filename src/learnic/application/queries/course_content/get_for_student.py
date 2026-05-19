from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
    CourseReleaseReader,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.capabilities import ProductCapability
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
        enrollment_gateway: EnrollmentGateway,
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
        if product is None or not product.supports(
            ProductCapability.HAS_COURSE_CONTENT,
        ):
            # Webinar products are intentionally hidden under the
            # course-content endpoint — surface as 404 rather than
            # leaking type info via a separate error.
            raise EntityNotFoundError(data.product_id)

        enrollment = await self._enrollment_gateway.with_product_and_student(
            data.product_id,
            data.actor_id,
        )
        if enrollment is None or enrollment.status is EnrollmentStatus.REFUNDED:
            raise EntityNotFoundError(data.product_id)
        # Course-flow gating above guarantees a course enrollment;
        # the gateway hydrates ``course_details`` from the
        # side-detail table.
        assert enrollment.course_details is not None  # noqa: S101

        view = await self._release_reader.get_content(
            enrollment.course_details.release_id,
        )
        if view is None:
            # Enrollment row exists but the pinned release is
            # missing — invariant violation; surface as 404 so
            # the client retries / contacts support.
            raise EntityNotFoundError(
                enrollment.course_details.release_id,
            )
        return view
