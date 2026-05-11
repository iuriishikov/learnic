from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInUnreleasedCourseError,
    EntityNotFoundError,
)
from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class EnrollStudentInCourseCommand:
    student_id: UserID
    product_id: ProductID


@final
class EnrollStudentInCourseCommandHandler:
    """Records the current user as enrolled in a self-paced course.

    Pre-conditions:
        * The product exists and ``type == COURSE``.
        * The course has at least one release (otherwise content
          is not yet defined and we wouldn't know what version
          to pin the student to).
        * The student has no existing enrollment for the same product.

    The enrollment captures the latest release id at signup time
    — students stay on that snapshot version forever (strict
    pinning, no opt-in upgrade in this phase).
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        enrollment_gateway: CourseEnrollmentGateway,
        release_gateway: CourseReleaseGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_gateway: Final = release_gateway

    async def run(
        self,
        data: EnrollStudentInCourseCommand,
    ) -> CourseEnrollmentID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        product.require_supports(ProductCapability.HAS_COURSE_ENROLLMENT)
        existing = await self._enrollment_gateway.with_product_and_student(
            data.product_id,
            data.student_id,
        )
        if existing is not None:
            raise AlreadyEnrolledError(
                data.product_id,
                data.student_id,
            )
        latest_release = await self._release_gateway.latest_for_product(
            data.product_id,
        )
        if latest_release is None:
            raise CannotEnrollInUnreleasedCourseError(data.product_id)

        enrollment = CourseEnrollment.create(
            product_id=data.product_id,
            student_id=data.student_id,
            release_id=latest_release.oid,
        )
        self._entity_saver.add_one(enrollment)
        await self._transaction.commit()
        return enrollment.oid
