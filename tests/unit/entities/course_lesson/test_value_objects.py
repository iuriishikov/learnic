import pytest

from learnic.entities.course_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.course_lesson.errors import (
    CourseLessonFieldTooLongError,
    EmptyCourseLessonFieldError,
)
from learnic.entities.course_lesson.value_objects import LessonTitle


class TestLessonTitle:
    def test_accepts_valid(self) -> None:
        assert LessonTitle("Lesson 1").value == "Lesson 1"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyCourseLessonFieldError) as exc:
            LessonTitle("   ")
        assert exc.value.field == "title"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(CourseLessonFieldTooLongError):
            LessonTitle("x" * (LESSON_TITLE_MAX_LEN + 1))
