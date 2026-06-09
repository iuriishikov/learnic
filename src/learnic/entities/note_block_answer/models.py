"""Persisted learner submission against an interactive release block.

A logged-in student's *latest* answer to one interactive block is
stored so their progress survives a reload — the SPA can restore the
selection and the correct/incorrect verdict instead of starting from
a blank slate every visit. There is exactly one row per
``(student, release block)``: re-answering overwrites it (the gateway
upserts), so this is "where the learner currently stands", not an
attempt history.

The stored ``submission`` mirrors the three interactive block kinds
(single / multi choice, text input). It deliberately re-declares its
own carrier dataclasses rather than importing the application-layer
``AnswerPayload`` — entities never depend on ``application``.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from typing_extensions import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_block_answer.ids import NoteBlockAnswerID
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.user.models import UserID

__all__ = [
    "NoteBlockAnswer",
    "SubmittedAnswer",
    "SubmittedMultiChoice",
    "SubmittedSingleChoice",
    "SubmittedTextAnswer",
]


@dataclass(slots=True, frozen=True)
class SubmittedSingleChoice:
    """The option the student picked on a single-choice block."""

    option_id: ChoiceOptionID


@dataclass(slots=True, frozen=True)
class SubmittedMultiChoice:
    """The set of options the student picked on a multi-choice block."""

    option_ids: frozenset[ChoiceOptionID]


@dataclass(slots=True, frozen=True)
class SubmittedTextAnswer:
    """The verbatim text the student typed on a text-input block."""

    answer: str


SubmittedAnswer = (
    SubmittedSingleChoice | SubmittedMultiChoice | SubmittedTextAnswer
)


@dataclass
class NoteBlockAnswer(BaseEntity[NoteBlockAnswerID]):
    """One student's current answer to one interactive release block.

    ``block_id`` is the **release-side** block id (the one the student
    received via the read endpoint). ``release_id`` is the release the
    student is pinned to — answers are scoped per release so switching
    release versions does not bleed progress across snapshots.
    """

    user_id: UserID
    block_id: LessonBlockID
    release_id: NoteReleaseID
    submission: SubmittedAnswer
    is_correct: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def record(
        cls,
        *,
        user_id: UserID,
        block_id: LessonBlockID,
        release_id: NoteReleaseID,
        submission: SubmittedAnswer,
        is_correct: bool,
    ) -> Self:
        """Build a fresh submission record stamped with the current time.

        The ``oid`` is only consumed on first insert — the gateway
        upserts on ``(user_id, block_id)`` and keeps the existing row's
        id on conflict, so re-answers reuse the original ``oid``.
        """
        now = datetime.now(timezone.utc)
        return cls(
            oid=NoteBlockAnswerID(uuid.uuid4()),
            user_id=user_id,
            block_id=block_id,
            release_id=release_id,
            submission=submission,
            is_correct=is_correct,
            created_at=now,
            updated_at=now,
        )
