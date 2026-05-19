from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    CourseEnrollmentTarget,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class EnrollStudentInCourseCommand:
    student_id: UserID
    product_id: ProductID


@final
class EnrollStudentInCourseCommandHandler:
    """Self-enroll the current student into a course product.

    Thin wrapper: builds a :class:`CourseEnrollmentTarget` from
    the HTTP command and delegates to :class:`EnrollmentService`.
    All type-specific work (release pinning, capability check)
    lives in :class:`CourseEnrollmentStrategy`.
    """

    def __init__(self, service: EnrollmentService) -> None:
        self._service: Final = service

    async def run(
        self,
        data: EnrollStudentInCourseCommand,
    ) -> EnrollmentID:
        return await self._service.enroll(
            student_id=data.student_id,
            target=CourseEnrollmentTarget(product_id=data.product_id),
        )
