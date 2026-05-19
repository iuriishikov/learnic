from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.enrollment import (
    EnrollmentReader,
    EnrollmentView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetStudentEnrollmentsQuery:
    student_id: UserID


@final
class GetStudentEnrollmentsQueryHandler:
    """List all enrollments of the current student.

    Returns both course and webinar enrollments unified —
    consumers (SPA) discriminate on
    :class:`EnrollmentView.type`. Replaces the two previous
    type-specific "list mine" endpoints.
    """

    def __init__(self, reader: EnrollmentReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetStudentEnrollmentsQuery,
    ) -> list[EnrollmentView]:
        return await self._reader.for_student(data.student_id)
