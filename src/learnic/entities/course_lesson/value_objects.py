from learnic.entities.common.value_object import ValueObject
from learnic.entities.course_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.course_lesson.errors import (
    CourseLessonFieldTooLongError,
    EmptyCourseLessonFieldError,
)


class LessonTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyCourseLessonFieldError("title")
        if len(self.value) > LESSON_TITLE_MAX_LEN:
            raise CourseLessonFieldTooLongError(
                "title",
                LESSON_TITLE_MAX_LEN,
            )
