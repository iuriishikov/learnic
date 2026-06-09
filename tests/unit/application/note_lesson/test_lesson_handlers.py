import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.note_lesson.add import (
    AddNoteLessonCommand,
    AddNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.delete import (
    DeleteNoteLessonCommand,
    DeleteNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.move import (
    MoveNoteLessonCommand,
    MoveNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.rename import (
    RenameNoteLessonCommand,
    RenameNoteLessonCommandHandler,
)
from learnic.application.commands.note_lesson.reorder import (
    ReorderNoteLessonsCommand,
    ReorderNoteLessonsCommandHandler,
)
from learnic.application.common.errors import (
    CrossNoteLessonMoveError,
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidReorderError,
)
from learnic.entities.file.ids import FileID
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_module.models import NoteModule
from learnic.entities.note_module.value_objects import ModuleTitle
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_module_gateway.with_id.return_value = note_module
    fake_product_gateway.with_id.return_value = note_product
    existing = NoteLesson.create(
        module_id=NoteModuleID(note_module.oid),
        product_id=ProductID(note_product.oid),
        title=LessonTitle("L1"),
        position=0,
    )
    fake_lesson_gateway.for_module.return_value = [existing]
    handler = AddNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddNoteLessonCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
            title="L2",
        ),
    )
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, NoteLesson)
    assert saved.oid == oid
    assert saved.position == 1
    assert saved.title.value == "L2"
    assert saved.product_id == note_product.oid
    fake_transaction.commit.assert_awaited_once()


# ---- rename ----


async def test_rename_lesson_updates_title(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    handler = RenameNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        RenameNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            title="Renamed",
        ),
    )
    assert note_lesson.title.value == "Renamed"
    fake_transaction.commit.assert_awaited_once()


async def test_rename_lesson_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    other_user_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_lessons",
    )
    handler = RenameNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            RenameNoteLessonCommand(
                actor_id=other_user_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                title="X",
            ),
        )
    fake_transaction.commit.assert_not_called()


# ---- move ----


async def test_move_lesson_to_other_module_same_note(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    note_module: NoteModule,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    target_module = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("Target"),
        position=1,
    )
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_module_gateway.with_id.return_value = target_module
    fake_product_gateway.with_id.return_value = note_product
    fake_lesson_gateway.for_module.return_value = []
    handler = MoveNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        MoveNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            target_module_id=NoteModuleID(target_module.oid),
        ),
    )
    assert note_lesson.module_id == target_module.oid
    assert note_lesson.position == 0
    fake_transaction.commit.assert_awaited_once()


async def test_move_lesson_cross_note_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    other_note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    foreign_module = NoteModule.create(
        product_id=ProductID(other_note_product.oid),
        title=ModuleTitle("Foreign"),
        position=0,
    )
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_module_gateway.with_id.return_value = foreign_module
    fake_product_gateway.with_id.return_value = note_product
    handler = MoveNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(CrossNoteLessonMoveError):
        await handler.run(
            MoveNoteLessonCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(note_lesson.oid),
                target_module_id=NoteModuleID(foreign_module.oid),
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
    note_product: Product,
    note_module: NoteModule,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_module_gateway.with_id.return_value = note_module
    fake_product_gateway.with_id.return_value = note_product
    handler = MoveNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        MoveNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
            target_module_id=NoteModuleID(note_module.oid),
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    a = NoteLesson.create(
        module_id=NoteModuleID(note_module.oid),
        product_id=ProductID(note_product.oid),
        title=LessonTitle("A"),
        position=0,
    )
    b = NoteLesson.create(
        module_id=NoteModuleID(note_module.oid),
        product_id=ProductID(note_product.oid),
        title=LessonTitle("B"),
        position=1,
    )
    fake_module_gateway.with_id.return_value = note_module
    fake_product_gateway.with_id.return_value = note_product
    fake_lesson_gateway.for_module.return_value = [a, b]
    handler = ReorderNoteLessonsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        ReorderNoteLessonsCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
            ordered_ids=[
                NoteLessonID(b.oid),
                NoteLessonID(a.oid),
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_module_gateway.with_id.return_value = note_module
    fake_product_gateway.with_id.return_value = note_product
    fake_lesson_gateway.for_module.return_value = []
    handler = ReorderNoteLessonsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        lesson_gateway=fake_lesson_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderNoteLessonsCommand(
                actor_id=author_id,
                module_id=NoteModuleID(note_module.oid),
                ordered_ids=[NoteLessonID(uuid.uuid4())],
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
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    handler = DeleteNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        files_reader=fake_files_reader,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )

    await handler.run(
        DeleteNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
        ),
    )
    fake_lesson_gateway.delete.assert_awaited_once_with(note_lesson)
    fake_transaction.commit.assert_awaited_once()


async def test_delete_lesson_with_files_sweeps_and_publishes_quota(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    file_a = FileID(uuid.uuid4())
    file_b = FileID(uuid.uuid4())
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_files_reader.file_ids_for_lesson.return_value = [file_a, file_b]

    # Shared parent so we can assert relative call ordering between
    # the file-ref snapshot and the cascading delete.
    recorder = MagicMock()
    recorder.attach_mock(
        fake_files_reader.file_ids_for_lesson,
        "file_ids_for_lesson",
    )
    recorder.attach_mock(fake_lesson_gateway.delete, "delete")

    handler = DeleteNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        files_reader=fake_files_reader,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )

    await handler.run(
        DeleteNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
        ),
    )

    # One soft-delete per snapshotted file id.
    assert fake_file_uploads.soft_delete_previous.await_count == 2
    swept = [
        call.args[0]
        for call in fake_file_uploads.soft_delete_previous.await_args_list
    ]
    assert swept == [file_a, file_b]

    fake_lesson_gateway.delete.assert_awaited_once_with(note_lesson)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()

    # Quota is published once, AFTER commit, keyed by the note author.
    fake_quota_publisher.usage_changed.assert_awaited_once_with(
        note_product.author_id,
    )

    # The file-ref snapshot must precede the cascading delete —
    # afterwards the block rows are gone and the walk returns nothing.
    ordered = [name for name, _, _ in recorder.mock_calls]
    assert ordered.index("file_ids_for_lesson") < ordered.index("delete")


async def test_delete_lesson_without_files_skips_quota(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    note_product: Product,
    note_lesson: NoteLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = note_lesson
    fake_product_gateway.with_id.return_value = note_product
    fake_files_reader.file_ids_for_lesson.return_value = []
    handler = DeleteNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        files_reader=fake_files_reader,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )

    await handler.run(
        DeleteNoteLessonCommand(
            actor_id=author_id,
            lesson_id=NoteLessonID(note_lesson.oid),
        ),
    )

    fake_file_uploads.soft_delete_previous.assert_not_awaited()
    fake_quota_publisher.usage_changed.assert_not_awaited()
    # Content event still fires even when no files were touched.
    fake_event_bus.publish.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_delete_lesson_missing_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_quota_publisher: AsyncMock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = None
    handler = DeleteNoteLessonCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        files_reader=fake_files_reader,
        file_uploads=fake_file_uploads,
        event_bus=fake_event_bus,
        quota_publisher=fake_quota_publisher,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            DeleteNoteLessonCommand(
                actor_id=author_id,
                lesson_id=NoteLessonID(uuid.uuid4()),
            ),
        )
