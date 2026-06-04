import pytest

from learnic.entities.note_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.note_lesson.errors import (
    NoteLessonFieldTooLongError,
    EmptyNoteLessonFieldError,
)
from learnic.entities.note_lesson.value_objects import LessonTitle


class TestLessonTitle:
    def test_accepts_valid(self) -> None:
        assert LessonTitle("Lesson 1").value == "Lesson 1"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyNoteLessonFieldError) as exc:
            LessonTitle("   ")
        assert exc.value.field == "title"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(NoteLessonFieldTooLongError):
            LessonTitle("x" * (LESSON_TITLE_MAX_LEN + 1))
