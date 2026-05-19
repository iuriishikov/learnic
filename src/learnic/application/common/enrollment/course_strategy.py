from typing import ClassVar, Final, final

from typing_extensions import override

from learnic.application.common.enrollment.strategies import (
    CourseEnrollmentTarget,
    EnrollmentStrategy,
    EnrollmentTarget,
)
from learnic.application.common.errors import (
    CannotEnrollInUnreleasedCourseError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseGateway,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.user.models import UserID


@final
class CourseEnrollmentStrategy(EnrollmentStrategy):
    """Concrete strategy for ``EnrollmentKind.COURSE``.

    Pre-conditions:

    * Product exists and supports
      ``ProductCapability.HAS_COURSE_ENROLLMENT`` (i.e. is a
      ``COURSE``-kind product).
    * The course has at least one release — otherwise the
      enrollment can't be pinned to a release version.

    Constructs the :class:`Enrollment` via
    ``Enrollment.create_course`` (which also builds the
    ``CourseEnrollmentDetails`` body) and stages persistence
    through :class:`EnrollmentGateway.add` — the gateway owns the
    cross-table insert because the polymorphic ``details`` body
    is not mapped imperatively. The surrounding transaction
    commit is the service's responsibility.
    """

    enrollment_kind: ClassVar[EnrollmentKind] = EnrollmentKind.COURSE

    def __init__(
        self,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
        release_gateway: CourseReleaseGateway,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_gateway: Final = release_gateway

    @override
    async def find_existing(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment | None:
        assert isinstance(target, CourseEnrollmentTarget)  # noqa: S101
        return await self._enrollment_gateway.with_product_and_student(
            target.product_id,
            student_id,
        )

    @override
    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment:
        assert isinstance(target, CourseEnrollmentTarget)  # noqa: S101
        product = await self._product_gateway.with_id(target.product_id)
        if product is None:
            raise EntityNotFoundError(target.product_id)
        product.require_supports(
            ProductCapability.HAS_COURSE_ENROLLMENT,
        )
        latest_release = await self._release_gateway.latest_for_product(
            target.product_id,
        )
        if latest_release is None:
            raise CannotEnrollInUnreleasedCourseError(target.product_id)

        enrollment = Enrollment.create_course(
            student_id=student_id,
            product_id=target.product_id,
            release_id=latest_release.oid,
        )
        await self._enrollment_gateway.add(enrollment)
        return enrollment
