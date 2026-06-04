import uuid

from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.product.ids import ProductID


def _module_id() -> NoteModuleID:
    return NoteModuleID(uuid.uuid4())


def _product_id() -> ProductID:
    return ProductID(uuid.uuid4())


class TestCreate:
    def test_initial_state(self) -> None:
        lesson = NoteLesson.create(
            module_id=_module_id(),
            product_id=_product_id(),
            title=LessonTitle("Lesson"),
            position=0,
        )
        assert lesson.title.value == "Lesson"
        assert lesson.position == 0


class TestMutators:
    def test_rename(self) -> None:
        lesson = NoteLesson.create(
            module_id=_module_id(),
            product_id=_product_id(),
            title=LessonTitle("Old"),
            position=0,
        )
        lesson.rename(LessonTitle("New"))
        assert lesson.title.value == "New"

    def test_move_to_module_updates_module_and_position(self) -> None:
        lesson = NoteLesson.create(
            module_id=_module_id(),
            product_id=_product_id(),
            title=LessonTitle("L"),
            position=2,
        )
        new_module = _module_id()
        lesson.move_to_module(new_module, 0)
        assert lesson.module_id == new_module
        assert lesson.position == 0

    def test_change_position(self) -> None:
        lesson = NoteLesson.create(
            module_id=_module_id(),
            product_id=_product_id(),
            title=LessonTitle("L"),
            position=0,
        )
        lesson.change_position(7)
        assert lesson.position == 7
