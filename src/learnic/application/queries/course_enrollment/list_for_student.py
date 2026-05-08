from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentReader,
    CourseEnrollmentView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetStudentCourseEnrollmentsQuery:
    student_id: UserID


@final
class GetStudentCourseEnrollmentsQueryHandler:
    def __init__(self, reader: CourseEnrollmentReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetStudentCourseEnrollmentsQuery,
    ) -> list[CourseEnrollmentView]:
        return await self._reader.for_student(data.student_id)
