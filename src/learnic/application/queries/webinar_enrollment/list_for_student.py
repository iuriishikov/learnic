from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentReader,
    WebinarEnrollmentView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetStudentWebinarEnrollmentsQuery:
    student_id: UserID


@final
class GetStudentWebinarEnrollmentsQueryHandler:
    def __init__(self, reader: WebinarEnrollmentReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetStudentWebinarEnrollmentsQuery,
    ) -> list[WebinarEnrollmentView]:
        return await self._reader.for_student(data.student_id)
