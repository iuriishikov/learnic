from learnic.entities.common.value_object import ValueObject
from learnic.entities.note_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.note_lesson.errors import (
    NoteLessonFieldTooLongError,
    EmptyNoteLessonFieldError,
)


class LessonTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNoteLessonFieldError("title")
        if len(self.value) > LESSON_TITLE_MAX_LEN:
            raise NoteLessonFieldTooLongError(
                "title",
                LESSON_TITLE_MAX_LEN,
            )
