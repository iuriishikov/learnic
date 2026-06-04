from learnic.entities.common.errors import FieldError


class EmptyNoteModuleFieldError(FieldError):
    """Raised when a required string-like note-module field is empty."""

    field: str


class NoteModuleFieldTooLongError(FieldError):
    """Raised when a string-like note-module field exceeds its max length."""

    field: str
    limit: int
