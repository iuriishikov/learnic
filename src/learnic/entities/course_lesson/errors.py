from learnic.entities.common.errors import FieldError


class EmptyCourseLessonFieldError(FieldError):
    """Raised when a required string-like course-lesson field is empty."""

    field: str


class CourseLessonFieldTooLongError(FieldError):
    """Raised when a string-like course-lesson field exceeds its max length."""

    field: str
    limit: int
