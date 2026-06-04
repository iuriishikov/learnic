"""Reveal-on-demand for the correct answer of an interactive block.

Reveal is a separate explicit action — distinct from check —
because returning the correct answer alongside a wrong check
response would be a one-shot backdoor (submit junk, read the
correct answer). Reveal forces the student to commit to "I
give up, show me." which can be logged and rate-limited
independently.

Same enrollment gate as check. Same v1 caveats: no persistence
of reveal events, no rate limiting.
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
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_block.models import (
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RevealedSingleChoice:
    option_id: ChoiceOptionID


@dataclass(slots=True, frozen=True)
class RevealedMultiChoice:
    option_ids: frozenset[ChoiceOptionID]


@dataclass(slots=True, frozen=True)
class RevealedTextAnswers:
    """All accepted spellings, so the SPA can show the spectrum."""

    answers: tuple[str, ...]


RevealedAnswer = RevealedSingleChoice | RevealedMultiChoice | RevealedTextAnswers


@dataclass(slots=True, frozen=True)
class RevealBlockAnswerCommand:
    actor_id: UserID
    block_id: LessonBlockID


@final
class RevealBlockAnswerCommandHandler:
    def __init__(
        self,
        release_block_gateway: NoteReleaseBlockGateway,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
    ) -> None:
        self._release_block_gateway: Final = release_block_gateway
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway

    async def run(self, data: RevealBlockAnswerCommand) -> RevealedAnswer:
        block = await self._release_block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)

        product = await self._product_gateway.with_id(block.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            raise EntityNotFoundError(data.block_id)

        enrollment = await self._enrollment_gateway.with_product_and_student(
            block.product_id,
            data.actor_id,
        )
        if enrollment is None or enrollment.status is not EnrollmentStatus.ACTIVE:
            raise EntityNotFoundError(data.block_id)

        if isinstance(block, SingleChoiceBlock):
            return RevealedSingleChoice(option_id=block.correct_option_id)
        if isinstance(block, MultiChoiceBlock):
            return RevealedMultiChoice(option_ids=block.correct_option_ids)
        if isinstance(block, TextInputBlock):
            return RevealedTextAnswers(
                answers=tuple(a.value for a in block.accepted_answers),
            )
        raise WrongBlockTypeError(
            data.block_id,
            expected="single_choice|multi_choice|text_input",
            actual=block.type.value,
        )
