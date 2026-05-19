import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.course_block._inputs import (
    ChoiceOptionDraftInput,
)
from learnic.application.commands.course_block.add_multi_choice import (
    AddMultiChoiceBlockCommand,
    AddMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_single_choice import (
    AddSingleChoiceBlockCommand,
    AddSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.add_text_input import (
    AddTextInputBlockCommand,
    AddTextInputBlockCommandHandler,
)
from learnic.application.commands.course_block.update_multi_choice import (
    UpdateMultiChoiceBlockCommand,
    UpdateMultiChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_single_choice import (
    UpdateSingleChoiceBlockCommand,
    UpdateSingleChoiceBlockCommandHandler,
)
from learnic.application.commands.course_block.update_text_input import (
    UpdateTextInputBlockCommand,
    UpdateTextInputBlockCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    WrongBlockTypeError,
)
from learnic.entities.course_block.errors import (
    DuplicateAcceptedAnswerError,
    EmptyCorrectOptionsError,
    MultipleCorrectOptionsInSingleChoiceError,
)
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import (
    HtmlBlock,
    MultiChoiceBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


def _opt(label: str, *, is_correct: bool = False) -> ChoiceOptionDraftInput:
    return ChoiceOptionDraftInput(label=label, is_correct=is_correct)


# ============================== single choice ============================== #


async def test_add_single_choice_appends_and_picks_correct(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = [html_block]
    handler = AddSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddSingleChoiceBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            options=(
                _opt("Paris", is_correct=True),
                _opt("Berlin"),
                _opt("Madrid"),
            ),
        ),
    )
    fake_block_gateway.add_single_choice.assert_awaited_once()
    saved = fake_block_gateway.add_single_choice.call_args.args[0]
    assert isinstance(saved, SingleChoiceBlock)
    assert saved.oid == oid
    assert saved.position == 1  # next after the existing html_block
    assert [o.label.value for o in saved.options] == ["Paris", "Berlin", "Madrid"]
    # Correct id must equal the freshly-minted Paris-option's id.
    assert saved.correct_option_id == saved.options[0].oid
    fake_transaction.commit.assert_awaited_once()


async def test_add_single_choice_rejects_zero_correct(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = AddSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(EmptyCorrectOptionsError):
        await handler.run(
            AddSingleChoiceBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                options=(_opt("a"), _opt("b")),
            ),
        )
    fake_block_gateway.add_single_choice.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_add_single_choice_rejects_multiple_correct(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = AddSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(MultipleCorrectOptionsInSingleChoiceError):
        await handler.run(
            AddSingleChoiceBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                options=(
                    _opt("a", is_correct=True),
                    _opt("b", is_correct=True),
                ),
            ),
        )
    fake_block_gateway.add_single_choice.assert_not_awaited()


async def test_add_single_choice_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    other_user_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="edit_lessons",
    )
    handler = AddSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddSingleChoiceBlockCommand(
                actor_id=other_user_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                options=(_opt("a", is_correct=True), _opt("b")),
            ),
        )
    fake_block_gateway.add_single_choice.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_update_single_choice_replaces_options(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    single_choice_block: SingleChoiceBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = single_choice_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateSingleChoiceBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(single_choice_block.oid),
            options=(_opt("New A"), _opt("New B", is_correct=True)),
        ),
    )
    fake_block_gateway.update_single_choice.assert_awaited_once_with(
        single_choice_block,
    )
    assert [o.label.value for o in single_choice_block.options] == ["New A", "New B"]
    assert single_choice_block.correct_option_id == single_choice_block.options[1].oid
    fake_transaction.commit.assert_awaited_once()


async def test_update_single_choice_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    handler = UpdateSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateSingleChoiceBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                options=(_opt("a", is_correct=True), _opt("b")),
            ),
        )
    fake_block_gateway.update_single_choice.assert_not_awaited()


async def test_update_single_choice_missing_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = None
    handler = UpdateSingleChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            UpdateSingleChoiceBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(uuid.uuid4()),
                options=(_opt("a", is_correct=True), _opt("b")),
            ),
        )


# ============================== multi choice ============================== #


async def test_add_multi_choice_picks_correct_subset(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddMultiChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddMultiChoiceBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            options=(
                _opt("Python", is_correct=True),
                _opt("Rust", is_correct=True),
                _opt("PHP"),
            ),
        ),
    )
    fake_block_gateway.add_multi_choice.assert_awaited_once()
    saved = fake_block_gateway.add_multi_choice.call_args.args[0]
    assert isinstance(saved, MultiChoiceBlock)
    assert saved.oid == oid
    assert saved.position == 0
    # Correct set = first two options' ids; order doesn't matter.
    assert saved.correct_option_ids == frozenset(
        {saved.options[0].oid, saved.options[1].oid},
    )


async def test_add_multi_choice_rejects_zero_correct(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = AddMultiChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(EmptyCorrectOptionsError):
        await handler.run(
            AddMultiChoiceBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                options=(_opt("a"), _opt("b")),
            ),
        )
    fake_block_gateway.add_multi_choice.assert_not_awaited()


async def test_add_multi_choice_accepts_all_correct(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    # All-correct is valid (unusual but the entity invariant doesn't
    # forbid it — author may craft a "pick all that apply: all of
    # the above" prompt).
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddMultiChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        AddMultiChoiceBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            options=(
                _opt("a", is_correct=True),
                _opt("b", is_correct=True),
            ),
        ),
    )
    saved = fake_block_gateway.add_multi_choice.call_args.args[0]
    assert len(saved.correct_option_ids) == 2


async def test_update_multi_choice_replaces_options(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    multi_choice_block: MultiChoiceBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = multi_choice_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateMultiChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateMultiChoiceBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(multi_choice_block.oid),
            options=(
                _opt("X", is_correct=True),
                _opt("Y"),
                _opt("Z", is_correct=True),
            ),
        ),
    )
    assert [o.label.value for o in multi_choice_block.options] == ["X", "Y", "Z"]
    assert multi_choice_block.correct_option_ids == frozenset(
        {multi_choice_block.options[0].oid, multi_choice_block.options[2].oid},
    )
    fake_transaction.commit.assert_awaited_once()


async def test_update_multi_choice_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    handler = UpdateMultiChoiceBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateMultiChoiceBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                options=(_opt("a", is_correct=True), _opt("b")),
            ),
        )


# ============================== text input ============================== #


async def test_add_text_input_appends(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddTextInputBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddTextInputBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            accepted_answers=("Paris", "Paname"),
            case_sensitive=False,
            trim_whitespace=True,
        ),
    )
    fake_block_gateway.add_text_input.assert_awaited_once()
    saved = fake_block_gateway.add_text_input.call_args.args[0]
    assert isinstance(saved, TextInputBlock)
    assert saved.oid == oid
    assert saved.position == 0
    assert [a.value for a in saved.accepted_answers] == ["Paris", "Paname"]
    assert saved.case_sensitive is False
    assert saved.trim_whitespace is True
    fake_transaction.commit.assert_awaited_once()


async def test_add_text_input_propagates_duplicate_error(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    # Duplicate-under-normalisation invariant lives on the entity;
    # the handler simply lets the FieldError bubble out so the
    # route translates it to HTTP 422.
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = AddTextInputBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(DuplicateAcceptedAnswerError):
        await handler.run(
            AddTextInputBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                accepted_answers=("Paris", " paris "),
                case_sensitive=False,
                trim_whitespace=True,
            ),
        )
    fake_block_gateway.add_text_input.assert_not_awaited()


async def test_update_text_input_replaces_answers_and_flags(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    text_input_block: TextInputBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = text_input_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateTextInputBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateTextInputBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(text_input_block.oid),
            accepted_answers=("London", "LONDON"),
            case_sensitive=True,
            trim_whitespace=False,
        ),
    )
    assert [a.value for a in text_input_block.accepted_answers] == [
        "London",
        "LONDON",
    ]
    assert text_input_block.case_sensitive is True
    assert text_input_block.trim_whitespace is False
    fake_transaction.commit.assert_awaited_once()


async def test_update_text_input_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    handler = UpdateTextInputBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateTextInputBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                accepted_answers=("x",),
                case_sensitive=False,
                trim_whitespace=True,
            ),
        )
