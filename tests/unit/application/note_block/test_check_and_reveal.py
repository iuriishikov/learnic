import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.note_block.check_answer import (
    BlockCheckResult,
    CheckBlockAnswerCommand,
    CheckBlockAnswerCommandHandler,
    MultiChoiceAnswerPayload,
    SingleChoiceAnswerPayload,
    TextAnswerPayload,
)
from learnic.application.commands.note_block.reveal_answer import (
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
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.note_block.ids import ChoiceOptionID, LessonBlockID
from learnic.entities.note_block.models import (
    HtmlBlock,
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@pytest.fixture
def pinned_release_id() -> NoteReleaseID:
    return NoteReleaseID(uuid.uuid4())


@pytest.fixture
def fake_release_block_gateway(
    pinned_release_id: NoteReleaseID,
) -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    # By default the block belongs to the student's pinned release; the
    # cross-release test overrides this to a different id.
    gw.release_id_for_block = AsyncMock(return_value=pinned_release_id)
    return gw


@pytest.fixture
def fake_enrollment_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_product_and_student = AsyncMock()
    return gw


@pytest.fixture
def fake_note_block_answer_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.upsert = AsyncMock()
    return gw


def _active_enrollment(
    student_id: UserID,
    product: Product,
    release_id: NoteReleaseID,
) -> Enrollment:
    return Enrollment.create_note(
        student_id=student_id,
        product_id=product.oid,
        release_id=release_id,
    )


def _make_check_handler(
    release_block_gateway: AsyncMock,
    product_gateway: AsyncMock,
    enrollment_gateway: AsyncMock,
    answer_gateway: AsyncMock,
    transaction: AsyncMock,
) -> CheckBlockAnswerCommandHandler:
    return CheckBlockAnswerCommandHandler(
        release_block_gateway=release_block_gateway,
        product_gateway=product_gateway,
        enrollment_gateway=enrollment_gateway,
        note_block_answer_gateway=answer_gateway,
        transaction=transaction,
    )


def _make_reveal_handler(
    release_block_gateway: AsyncMock,
    product_gateway: AsyncMock,
    enrollment_gateway: AsyncMock,
) -> RevealBlockAnswerCommandHandler:
    return RevealBlockAnswerCommandHandler(
        release_block_gateway=release_block_gateway,
        product_gateway=product_gateway,
        enrollment_gateway=enrollment_gateway,
    )


# ============================== check ============================== #


async def test_check_single_choice_correct(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    # Latest submission persisted against the pinned release + committed.
    fake_note_block_answer_gateway.upsert.assert_awaited_once()
    persisted = fake_note_block_answer_gateway.upsert.await_args.args[0]
    assert persisted.release_id == pinned_release_id
    fake_transaction.commit.assert_awaited_once()


async def test_check_single_choice_incorrect(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
    )
    wrong_id = next(
        o.oid
        for o in single_choice_block.options
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
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    multi_choice_block: MultiChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = multi_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    text_input_block: TextInputBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = text_input_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = None
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    other_user_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    # No enrollment for this user.
    fake_enrollment_gateway.with_product_and_student.return_value = None
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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


async def test_check_block_from_other_release_hidden_as_404(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    # Block belongs to a DIFFERENT release than the student is pinned to.
    fake_release_block_gateway.release_id_for_block.return_value = (
        NoteReleaseID(uuid.uuid4())
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CheckBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(single_choice_block.oid),
                payload=SingleChoiceAnswerPayload(
                    option_id=single_choice_block.correct_option_id,
                ),
            ),
        )
    fake_note_block_answer_gateway.upsert.assert_not_called()


async def test_check_payload_shape_mismatch_409(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    fake_note_block_answer_gateway: AsyncMock,
    fake_transaction: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_check_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
        fake_note_block_answer_gateway,
        fake_transaction,
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
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
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
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    multi_choice_block: MultiChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = multi_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
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
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    text_input_block: TextInputBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = text_input_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
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
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    other_user_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = None
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RevealBlockAnswerCommand(
                actor_id=other_user_id,
                block_id=LessonBlockID(single_choice_block.oid),
            ),
        )


async def test_reveal_block_from_other_release_hidden_as_404(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    fake_release_block_gateway.release_id_for_block.return_value = (
        NoteReleaseID(uuid.uuid4())
    )
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RevealBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(single_choice_block.oid),
            ),
        )


async def test_reveal_passive_block_409(
    fake_release_block_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    pinned_release_id: NoteReleaseID,
    note_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_release_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = note_product
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _active_enrollment(author_id, note_product, pinned_release_id)
    )
    handler = _make_reveal_handler(
        fake_release_block_gateway,
        fake_product_gateway,
        fake_enrollment_gateway,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            RevealBlockAnswerCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
            ),
        )
