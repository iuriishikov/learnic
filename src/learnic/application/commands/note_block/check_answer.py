"""Server-side answer check for interactive release blocks.

The student submits a payload (option id / id set / text) and
the handler resolves the release block, verifies enrollment,
runs :meth:`block.check` and returns a boolean. The correct
answer is NEVER serialised back — wrong responses get
``is_correct=False`` and nothing more. To see the correct
answer the student must invoke the separate ``reveal`` handler.

The payload variant is type-checked against the resolved block
type: sending a multi-choice payload to a single-choice block
yields :class:`WrongBlockTypeError` (HTTP 409). Unknown option
ids are silently treated as incorrect — they're not an error,
they're just wrong submissions.

The student's latest submission IS persisted (one row per
``(student, release block)``, upserted) so a logged-in learner's
progress survives a reload — wrong answers are stored too, so the
SPA can restore the selection together with the correct/incorrect
verdict. Persistence is keyed to the release the student is pinned
to. The handler publishes no domain events; rate limiting is out of
scope (relies on the ingress layer if any).
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseBlockGateway,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_block_answer import (
    NoteBlockAnswerGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_block.models import (
    LessonBlock,
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.note_block_answer.models import (
    NoteBlockAnswer,
    SubmittedAnswer,
    SubmittedMultiChoice,
    SubmittedSingleChoice,
    SubmittedTextAnswer,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SingleChoiceAnswerPayload:
    option_id: ChoiceOptionID


@dataclass(slots=True, frozen=True)
class MultiChoiceAnswerPayload:
    option_ids: frozenset[ChoiceOptionID]


@dataclass(slots=True, frozen=True)
class TextAnswerPayload:
    answer: str


AnswerPayload = (
    SingleChoiceAnswerPayload | MultiChoiceAnswerPayload | TextAnswerPayload
)


@dataclass(slots=True, frozen=True)
class CheckBlockAnswerCommand:
    """Verify a student's submission against the correct answer.

    ``block_id`` is the **release-side** block id (the one the
    student received via the read endpoint), not a draft id.
    """

    actor_id: UserID
    block_id: LessonBlockID
    payload: AnswerPayload


@dataclass(slots=True, frozen=True)
class BlockCheckResult:
    """Outcome of a check call. ``is_correct`` is the only signal."""

    is_correct: bool


@final
class CheckBlockAnswerCommandHandler:
    def __init__(
        self,
        release_block_gateway: NoteReleaseBlockGateway,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
        note_block_answer_gateway: NoteBlockAnswerGateway,
        transaction: Transaction,
    ) -> None:
        self._release_block_gateway: Final = release_block_gateway
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._answer_gateway: Final = note_block_answer_gateway
        self._transaction: Final = transaction

    async def run(self, data: CheckBlockAnswerCommand) -> BlockCheckResult:
        block = await self._release_block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)

        product = await self._product_gateway.with_id(block.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            # Same hiding policy as ``GetNoteContentQueryHandler``:
            # non-note products are surfaced as 404, not 409.
            raise EntityNotFoundError(data.block_id)

        enrollment = await self._enrollment_gateway.with_product_and_student(
            block.product_id,
            data.actor_id,
        )
        if enrollment is None or enrollment.status is not EnrollmentStatus.ACTIVE:
            # Treat absence-of-enrollment as "block not visible" —
            # consistent with the read endpoint, no separate 403.
            raise EntityNotFoundError(data.block_id)

        is_correct, submission = self._grade(block, data)

        # Persist the student's latest submission (correct or not) so
        # the SPA can restore the selection + verdict on reload. The
        # note-flow gating above guarantees a hydrated note enrollment,
        # so ``details`` carries the pinned release.
        assert isinstance(  # noqa: S101
            enrollment.details,
            NoteEnrollmentDetails,
        )
        await self._answer_gateway.upsert(
            NoteBlockAnswer.record(
                user_id=data.actor_id,
                block_id=data.block_id,
                release_id=enrollment.details.release_id,
                submission=submission,
                is_correct=is_correct,
            ),
        )
        await self._transaction.commit()
        return BlockCheckResult(is_correct=is_correct)

    def _grade(
        self,
        block: LessonBlock,
        data: CheckBlockAnswerCommand,
    ) -> tuple[bool, SubmittedAnswer]:
        """Grade ``data.payload`` against ``block`` and echo the submission.

        Returns the correctness flag plus the domain submission object
        to persist. The payload variant must match the block type —
        a mismatch (or a non-interactive block) raises
        :class:`WrongBlockTypeError` (HTTP 409).
        """
        if isinstance(block, SingleChoiceBlock):
            if not isinstance(data.payload, SingleChoiceAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.SINGLE_CHOICE.value,
                    actual=block.type.value,
                )
            return (
                block.check(data.payload.option_id),
                SubmittedSingleChoice(option_id=data.payload.option_id),
            )
        if isinstance(block, MultiChoiceBlock):
            if not isinstance(data.payload, MultiChoiceAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.MULTI_CHOICE.value,
                    actual=block.type.value,
                )
            return (
                block.check(data.payload.option_ids),
                SubmittedMultiChoice(option_ids=data.payload.option_ids),
            )
        if isinstance(block, TextInputBlock):
            if not isinstance(data.payload, TextAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.TEXT_INPUT.value,
                    actual=block.type.value,
                )
            return (
                block.check(data.payload.answer),
                SubmittedTextAnswer(answer=data.payload.answer),
            )
        # Block exists but is not an interactive type — passive
        # content (html / katex / video / code) has no answer to
        # check. Treat as a type mismatch (409) so the client gets
        # a precise reason rather than silent 404.
        raise WrongBlockTypeError(
            data.block_id,
            expected="single_choice|multi_choice|text_input",
            actual=block.type.value,
        )
