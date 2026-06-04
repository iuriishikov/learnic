from typing import Protocol

from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_module.ids import NoteModuleID


class NoteLessonGateway(Protocol):
    """Write-side lookups and persistence for :class:`NoteLesson`."""

    async def with_id(
        self,
        oid: NoteLessonID,
    ) -> NoteLesson | None: ...

    async def for_module(
        self,
        module_id: NoteModuleID,
    ) -> list[NoteLesson]:
        """Return all lessons of a module, ordered by position ascending."""
        ...

    async def lock_for_module(self, module_id: NoteModuleID) -> None:
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

    async def delete(self, lesson: NoteLesson) -> None: ...

    async def reorder(
        self,
        module_id: NoteModuleID,
        ordered_ids: list[NoteLessonID],
    ) -> None:
        """Atomic full-reorder of all lessons within a module.

        Caller must verify that ``ordered_ids`` is exactly the set
        of lesson ids belonging to the module.
        """
        ...
