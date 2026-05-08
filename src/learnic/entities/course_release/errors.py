from learnic.entities.common.errors import FieldError


class NegativeReleaseVersionError(FieldError):
    """Raised when constructing :class:`CourseReleaseVersion` with a negative component."""


class EmptyReleaseNotesError(FieldError):
    """Raised when release notes are explicitly empty (use ``None`` to omit)."""


class ReleaseNotesTooLongError(FieldError):
    """Raised when release notes exceed the max length."""

    limit: int
