from learnic.entities.common.errors import FieldError


class EmptyCourseModuleFieldError(FieldError):
    """Raised when a required string-like course-module field is empty."""

    field: str


class CourseModuleFieldTooLongError(FieldError):
    """Raised when a string-like course-module field exceeds its max length."""

    field: str
    limit: int
