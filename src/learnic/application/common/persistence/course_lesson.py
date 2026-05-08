from typing import Protocol

from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_module.ids import CourseModuleID


class CourseLessonGateway(Protocol):
    """Write-side lookups and persistence for :class:`CourseLesson`."""

    async def with_id(
        self,
        oid: CourseLessonID,
    ) -> CourseLesson | None: ...

    async def for_module(
        self,
        module_id: CourseModuleID,
    ) -> list[CourseLesson]:
        """Return all lessons of a module, ordered by position ascending."""
        ...

    async def delete(self, lesson: CourseLesson) -> None: ...

    async def reorder(
        self,
        module_id: CourseModuleID,
        ordered_ids: list[CourseLessonID],
    ) -> None:
        """Atomic full-reorder of all lessons within a module.

        Caller must verify that ``ordered_ids`` is exactly the set
        of lesson ids belonging to the module.
        """
        ...
