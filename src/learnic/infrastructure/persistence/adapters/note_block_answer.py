"""SQLAlchemy adapters for persisted learner block submissions.

The ``note_block_answers`` table is not ORM-mapped (its ``submission``
is polymorphic JSONB), so both adapters use Core statements with
explicit (de)serialisation — the same approach as the release-block
subtype tables. The gateway upserts on the ``(user_id, block_id)``
unique constraint; the reader projects rows back into domain views.
"""

from typing import Any, Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_block_answer import (
    NoteBlockAnswerGateway,
    NoteBlockAnswerReader,
    NoteBlockAnswerView,
)
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_block_answer.models import (
    NoteBlockAnswer,
    SubmittedAnswer,
    SubmittedMultiChoice,
    SubmittedSingleChoice,
    SubmittedTextAnswer,
)
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.note_block_answer import (
    note_block_answers_table,
)
from learnic.infrastructure.persistence.models.note_release import (
    note_release_blocks_table,
)

_SINGLE: Final = "single_choice"
_MULTI: Final = "multi_choice"
_TEXT: Final = "text_input"


def _submission_to_jsonb(submission: SubmittedAnswer) -> dict[str, Any]:
    if isinstance(submission, SubmittedSingleChoice):
        return {"type": _SINGLE, "option_id": str(submission.option_id)}
    if isinstance(submission, SubmittedMultiChoice):
        return {
            "type": _MULTI,
            # Sorted for a deterministic on-disk shape — a set has no
            # inherent order and correctness is set-based anyway.
            "option_ids": sorted(str(o) for o in submission.option_ids),
        }
    if isinstance(submission, SubmittedTextAnswer):
        return {"type": _TEXT, "answer": submission.answer}
    # Closed set: a new SubmittedAnswer variant must add a branch here
    # rather than silently mis-serialising as text (mirrors the loud
    # default in ``_submission_from_jsonb``).
    raise AssertionError(  # pragma: no cover
        f"Unhandled submission variant: {type(submission).__name__}",
    )


def _submission_from_jsonb(raw: dict[str, Any]) -> SubmittedAnswer:
    kind = raw["type"]
    if kind == _SINGLE:
        return SubmittedSingleChoice(
            option_id=ChoiceOptionID(UUID(raw["option_id"])),
        )
    if kind == _MULTI:
        return SubmittedMultiChoice(
            option_ids=frozenset(
                ChoiceOptionID(UUID(o)) for o in raw["option_ids"]
            ),
        )
    if kind == _TEXT:
        return SubmittedTextAnswer(answer=raw["answer"])
    raise ValueError(f"Unknown stored submission type: {kind!r}")


class NoteBlockAnswerMapperAlchemy(NoteBlockAnswerGateway):
    """Write-side upsert of a student's latest block submission."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def upsert(self, answer: NoteBlockAnswer) -> None:
        payload = _submission_to_jsonb(answer.submission)
        stmt = pg_insert(note_block_answers_table).values(
            oid=answer.oid,
            user_id=answer.user_id,
            block_id=answer.block_id,
            release_id=answer.release_id,
            payload=payload,
            is_correct=answer.is_correct,
            created_at=answer.created_at,
            updated_at=answer.updated_at,
        )
        # ``block_id`` is release-specific, so a (user, block) conflict
        # is always the same release — ``release_id`` / ``created_at`` /
        # ``oid`` stay put; only the submission, verdict and
        # ``updated_at`` move.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_note_block_answers_user_block",
            set_={
                "payload": payload,
                "is_correct": answer.is_correct,
                "updated_at": sa.func.now(),
            },
        )
        await self._session.execute(stmt)


class NoteBlockAnswerReaderAlchemy(NoteBlockAnswerReader):
    """Read-side projection of saved submissions for one release."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_release(
        self,
        user_id: UserID,
        release_id: NoteReleaseID,
    ) -> list[NoteBlockAnswerView]:
        a = note_block_answers_table
        b = note_release_blocks_table
        # Scope by the *block's* own release (joined), not the saved row's
        # denormalised ``release_id`` column. The stored column can lag the
        # block's true release if a check raced a self-repin, so trusting it
        # could surface an answer under a release whose content tree does not
        # contain the block. Joining keeps restore correct by construction —
        # an answer always lines up with the release its block belongs to.
        stmt = (
            sa.select(a.c.block_id, a.c.payload, a.c.is_correct)
            .join(b, b.c.oid == a.c.block_id)
            .where(a.c.user_id == user_id, b.c.release_id == release_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            NoteBlockAnswerView(
                block_id=LessonBlockID(row.block_id),
                submission=_submission_from_jsonb(row.payload),
                is_correct=row.is_correct,
            )
            for row in rows
        ]
