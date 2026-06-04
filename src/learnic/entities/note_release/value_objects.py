from typing import Self

from learnic.entities.common.value_object import ValueObject
from learnic.entities.note_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.errors import (
    EmptyReleaseNotesError,
    NegativeReleaseVersionError,
    ReleaseNotesTooLongError,
)


class NoteReleaseVersion(ValueObject):
    """Semver-style version triplet ``(major, minor, patch)``.

    Used both for display (``v2.1.3``) and for the unique
    constraint ``UNIQUE(product_id, major, minor, patch)``. The
    monotonic ``ordinal`` lives on the entity row, not the VO.
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise NegativeReleaseVersionError

    @classmethod
    def initial(cls) -> Self:
        """The implicit ``v0.0.0`` baseline before any release exists."""
        return cls(0, 0, 0)

    def bumped(self, kind: NoteReleaseKind) -> Self:
        cls = type(self)
        if kind is NoteReleaseKind.MAJOR:
            return cls(self.major + 1, 0, 0)
        if kind is NoteReleaseKind.MINOR:
            return cls(self.major, self.minor + 1, 0)
        return cls(self.major, self.minor, self.patch + 1)


class ReleaseNotes(ValueObject):
    """Optional human-readable notes attached to a release."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyReleaseNotesError
        if len(self.value) > RELEASE_NOTES_MAX_LEN:
            raise ReleaseNotesTooLongError(RELEASE_NOTES_MAX_LEN)
