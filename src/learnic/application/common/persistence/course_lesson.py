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

    async def lock_for_module(self, module_id: CourseModuleID) -> None:
        """Take a transaction-scoped advisory lock on ``module_id``.

        Serializes lesson position mutations (add / reorder / move)
        within a module across replicas so concurrent editors cannot
        compute colliding ``position`` values or clobber each other's
        reorder. Call FIRST in every such handler; for ``move`` lock
        only the target module (the source just loses a row and is
        not renumbered — locking one module per move also keeps moves
        deadlock-free). Auto-released on COMMIT / ROLLBACK. See
        :meth:`LessonBlockGateway.lock_for_lesson`.
        """
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
