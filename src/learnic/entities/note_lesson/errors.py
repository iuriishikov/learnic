from learnic.entities.common.errors import FieldError


class EmptyNoteLessonFieldError(FieldError):
    """Raised when a required string-like note-lesson field is empty."""

    field: str


class NoteLessonFieldTooLongError(FieldError):
    """Raised when a string-like note-lesson field exceeds its max length."""

    field: str
    limit: int
