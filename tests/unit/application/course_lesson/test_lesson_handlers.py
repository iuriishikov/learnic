import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.course_lesson.add import (
    AddCourseLessonCommand,
    AddCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.delete import (
    DeleteCourseLessonCommand,
    DeleteCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.move import (
    MoveCourseLessonCommand,
    MoveCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.rename import (
    RenameCourseLessonCommand,
    RenameCourseLessonCommandHandler,
)
from learnic.application.commands.course_lesson.reorder import (
    ReorderCourseLessonsCommand,
    ReorderCourseLessonsCommandHandler,
)
from learnic.application.common.errors import (
    CrossCourseLessonMoveError,
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidReorderError,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.models import CourseModule
from learnic.entities.course_module.value_objects import ModuleTitle
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


# ---- add ----


async def test_add_lesson_appends_at_next_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_module_gateway.with_id.return_value = course_module
    fake_product_gateway.with_id.return_value = course_product
    existing = CourseLesson.create(
        module_id=CourseModuleID(course_module.oid),
        product_id=ProductID(course_product.oid),
        title=LessonTitle("L1"),
        position=0,
    )
    fake_lesson_gateway.for_module.return_value = [existing]
    handler = AddCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddCourseLessonCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
            title="L2",
        ),
    )
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, CourseLesson)
    assert saved.oid == oid
    assert saved.position == 1
    assert saved.title.value == "L2"
    assert saved.product_id == course_product.oid
    fake_transaction.commit.assert_awaited_once()


# ---- rename ----


async def test_rename_lesson_updates_title(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = RenameCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        RenameCourseLessonCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            title="Renamed",
        ),
    )
    assert course_lesson.title.value == "Renamed"
    fake_transaction.commit.assert_awaited_once()


async def test_rename_lesson_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
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
    handler = RenameCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            RenameCourseLessonCommand(
                actor_id=other_user_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                title="X",
            ),
        )
    fake_transaction.commit.assert_not_called()


# ---- move ----


async def test_move_lesson_to_other_module_same_course(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    target_module = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("Target"),
        position=1,
    )
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_module_gateway.with_id.return_value = target_module
    fake_product_gateway.with_id.return_value = course_product
    fake_lesson_gateway.for_module.return_value = []
    handler = MoveCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        MoveCourseLessonCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            target_module_id=CourseModuleID(target_module.oid),
        ),
    )
    assert course_lesson.module_id == target_module.oid
    assert course_lesson.position == 0
    fake_transaction.commit.assert_awaited_once()


async def test_move_lesson_cross_course_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    foreign_module = CourseModule.create(
        product_id=ProductID(other_course_product.oid),
        title=ModuleTitle("Foreign"),
        position=0,
    )
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_module_gateway.with_id.return_value = foreign_module
    fake_product_gateway.with_id.return_value = course_product
    handler = MoveCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(CrossCourseLessonMoveError):
        await handler.run(
            MoveCourseLessonCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                target_module_id=CourseModuleID(foreign_module.oid),
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_move_lesson_to_same_module_is_noop(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_module_gateway.with_id.return_value = course_module
    fake_product_gateway.with_id.return_value = course_product
    handler = MoveCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        MoveCourseLessonCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            target_module_id=CourseModuleID(course_module.oid),
        ),
    )
    fake_transaction.commit.assert_not_called()


# ---- reorder ----


async def test_reorder_lessons_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    a = CourseLesson.create(
        module_id=CourseModuleID(course_module.oid),
        product_id=ProductID(course_product.oid),
        title=LessonTitle("A"),
        position=0,
    )
    b = CourseLesson.create(
        module_id=CourseModuleID(course_module.oid),
        product_id=ProductID(course_product.oid),
        title=LessonTitle("B"),
        position=1,
    )
    fake_module_gateway.with_id.return_value = course_module
    fake_product_gateway.with_id.return_value = course_product
    fake_lesson_gateway.for_module.return_value = [a, b]
    handler = ReorderCourseLessonsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        ReorderCourseLessonsCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
            ordered_ids=[
                CourseLessonID(b.oid),
                CourseLessonID(a.oid),
            ],
        ),
    )
    fake_lesson_gateway.reorder.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_reorder_lessons_mismatch_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_module_gateway.with_id.return_value = course_module
    fake_product_gateway.with_id.return_value = course_product
    fake_lesson_gateway.for_module.return_value = []
    handler = ReorderCourseLessonsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderCourseLessonsCommand(
                actor_id=author_id,
                module_id=CourseModuleID(course_module.oid),
                ordered_ids=[CourseLessonID(uuid.uuid4())],
            ),
        )
    fake_lesson_gateway.reorder.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


# ---- delete ----


async def test_delete_lesson_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = DeleteCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeleteCourseLessonCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
        ),
    )
    fake_lesson_gateway.delete.assert_awaited_once_with(course_lesson)
    fake_transaction.commit.assert_awaited_once()


async def test_delete_lesson_missing_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = None
    handler = DeleteCourseLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            DeleteCourseLessonCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(uuid.uuid4()),
            ),
        )
