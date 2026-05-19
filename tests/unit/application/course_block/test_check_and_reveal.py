import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.course_block.check_answer import (
    BlockCheckResult,
    CheckBlockAnswerCommand,
    CheckBlockAnswerCommandHandler,
    MultiChoiceAnswerPayload,
    SingleChoiceAnswerPayload,
    TextAnswerPayload,
)
from learnic.application.commands.course_block.reveal_answer import (
    RevealBlockAnswerCommand,
    RevealBlockAnswerCommandHandler,
    RevealedMultiChoice,
    RevealedSingleChoice,
    RevealedTextAnswers,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    WrongBlockTypeError,
)
from learnic.entities.course_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.course_block.models import (
    HtmlBlock,
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_release_block_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_enrollment_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_product_and_student = AsyncMock()
    return gw


def _active_enrollment(student_id: UserID, product: Product) -> Enrollment:
    return Enrollment.create_course(
        student_id=student_id,
        product_id=product.oid,
        release_id=CourseReleaseID(uuid.uuid4()),
    )


# ============================== check ============================== #


async def test_check_single_choice_correct(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    result = await handler.run(
        CheckBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(single_choice_block.oid),
            payload=SingleChoiceAnswerPayload(
                option_id=single_choice_block.correct_option_id,
            ),
        ),
    )
    assert result == BlockCheckResult(is_correct=True)


async def test_check_single_choice_incorrect(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    wrong_id = next(
        o.oid for o in single_choice_block.options
        if o.oid != single_choice_block.correct_option_id
    )
    result = await handler.run(
        CheckBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(single_choice_block.oid),
            payload=SingleChoiceAnswerPayload(option_id=wrong_id),
        ),
    )
    assert result.is_correct is False


async def test_check_multi_choice_exact_set(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    multi_choice_block: MultiChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = multi_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    result = await handler.run(
        CheckBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(multi_choice_block.oid),
            payload=MultiChoiceAnswerPayload(
                option_ids=multi_choice_block.correct_option_ids,
            ),
        ),
    )
    assert result.is_correct is True


async def test_check_text_input_normalises_default(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    text_input_block: TextInputBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = text_input_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    # The fixture's accepted answer is "Paris" with case-insensitive
    # default; "  paris  " should match after trim + casefold.
    result = await handler.run(
        CheckBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(text_input_block.oid),
            payload=TextAnswerPayload(answer="  paris  "),
        ),
    )
    assert result.is_correct is True


async def test_check_block_not_found_404(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = None
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CheckBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(uuid.uuid4()),
                payload=TextAnswerPayload(answer="x"),
            ),
        )


async def test_check_no_enrollment_hides_as_404(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    other_user_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    # No enrollment for this user.
    fake_enrollment_gateway.with_product_and_student.return_value = None
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CheckBlockAnswerCommand(
                actor_id=other_user_id,
                block_id=LessonBlockID(single_choice_block.oid),
                payload=SingleChoiceAnswerPayload(
                    option_id=ChoiceOptionID(uuid.uuid4()),
                ),
            ),
        )


async def test_check_payload_shape_mismatch_409(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    # Sending a TextAnswerPayload to a single-choice block.
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            CheckBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(single_choice_block.oid),
                payload=TextAnswerPayload(answer="anything"),
            ),
        )


async def test_check_passive_block_409(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = CheckBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            CheckBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                payload=TextAnswerPayload(answer="x"),
            ),
        )


# ============================== reveal ============================== #


async def test_reveal_single_choice_returns_correct_id(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = RevealBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    answer = await handler.run(
        RevealBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(single_choice_block.oid),
        ),
    )
    assert answer == RevealedSingleChoice(
        option_id=single_choice_block.correct_option_id,
    )


async def test_reveal_multi_choice_returns_full_set(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    multi_choice_block: MultiChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = multi_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = RevealBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    answer = await handler.run(
        RevealBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(multi_choice_block.oid),
        ),
    )
    assert isinstance(answer, RevealedMultiChoice)
    assert answer.option_ids == multi_choice_block.correct_option_ids


async def test_reveal_text_input_returns_all_spellings(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    text_input_block: TextInputBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = text_input_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = RevealBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    answer = await handler.run(
        RevealBlockAnswerCommand(
            actor_id=author_id,
            block_id=LessonBlockID(text_input_block.oid),
        ),
    )
    assert isinstance(answer, RevealedTextAnswers)
    assert "Paris" in answer.answers


async def test_reveal_no_enrollment_hides_as_404(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    other_user_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = None
    handler = RevealBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RevealBlockAnswerCommand(
                actor_id=other_user_id,
                block_id=LessonBlockID(single_choice_block.oid),
            ),
        )


async def test_reveal_passive_block_409(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = course_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, course_product)
    )
    handler = RevealBlockAnswerCommandHandler(
        release_block_gateway=fake_release_block_gateway,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            RevealBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
            ),
        )
