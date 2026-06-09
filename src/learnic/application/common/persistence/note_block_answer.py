"""CQRS persistence contracts for :class:`NoteBlockAnswer`.

Write side (:class:`NoteBlockAnswerGateway`) upserts a student's
latest submission for one interactive block. Read side
(:class:`NoteBlockAnswerReader`) returns the student's saved answers
for a release so the SPA can restore selections + verdicts on load.
"""

from dataclasses import dataclass
from typing import Protocol

from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block_answer.models import (
    NoteBlockAnswer,
    SubmittedAnswer,
)
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class NoteBlockAnswerView:
    """Read-side projection of a saved learner submission."""

    block_id: LessonBlockID
    submission: SubmittedAnswer
    is_correct: bool


class NoteBlockAnswerGateway(Protocol):
    """Write-side upsert for a student's latest block submission."""

    async def upsert(self, answer: NoteBlockAnswer) -> None:
        """Insert ``answer`` or overwrite the existing row.

        Conflict key is ``(user_id, block_id)`` — re-answering the same
        block replaces the previous submission, correctness, and
        ``updated_at`` while keeping the original row id and
        ``created_at``. Does not commit; the handler owns the
        transaction.
        """
        ...


class NoteBlockAnswerReader(Protocol):
    """Read-side queries returning :class:`NoteBlockAnswerView`."""

    async def for_release(
        self,
        user_id: UserID,
        release_id: NoteReleaseID,
    ) -> list[NoteBlockAnswerView]:
        """Return all of ``user_id``'s saved answers for ``release_id``."""
        ...
