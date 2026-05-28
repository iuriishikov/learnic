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

v1 does NOT persist attempts. The handler publishes no domain
events; rate limiting is out of scope for v1 (relies on the
ingress layer if any). Both decisions are intentional trade-offs
documented in the implementation plan.
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseBlockGateway,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.course_block.models import (
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
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
        release_block_gateway: CourseReleaseBlockGateway,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
    ) -> None:
        self._release_block_gateway: Final = release_block_gateway
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway

    async def run(self, data: CheckBlockAnswerCommand) -> BlockCheckResult:
        block = await self._release_block_gateway.with_id(data.block_id)
        if block is None:
            raise EntityNotFoundError(data.block_id)

        product = await self._product_gateway.with_id(block.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_COURSE_CONTENT,
        ):
            # Same hiding policy as ``GetCourseContentQueryHandler``:
            # non-course products are surfaced as 404, not 409.
            raise EntityNotFoundError(data.block_id)

        enrollment = await self._enrollment_gateway.with_product_and_student(
            block.product_id,
            data.actor_id,
        )
        if enrollment is None or enrollment.status is not EnrollmentStatus.ACTIVE:
            # Treat absence-of-enrollment as "block not visible" —
            # consistent with the read endpoint, no separate 403.
            raise EntityNotFoundError(data.block_id)

        if isinstance(block, SingleChoiceBlock):
            if not isinstance(data.payload, SingleChoiceAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.SINGLE_CHOICE.value,
                    actual=block.type.value,
                )
            return BlockCheckResult(
                is_correct=block.check(data.payload.option_id),
            )
        if isinstance(block, MultiChoiceBlock):
            if not isinstance(data.payload, MultiChoiceAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.MULTI_CHOICE.value,
                    actual=block.type.value,
                )
            return BlockCheckResult(
                is_correct=block.check(data.payload.option_ids),
            )
        if isinstance(block, TextInputBlock):
            if not isinstance(data.payload, TextAnswerPayload):
                raise WrongBlockTypeError(
                    data.block_id,
                    expected=BlockType.TEXT_INPUT.value,
                    actual=block.type.value,
                )
            return BlockCheckResult(
                is_correct=block.check(data.payload.answer),
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
