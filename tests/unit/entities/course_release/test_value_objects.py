import pytest

from learnic.entities.course_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.errors import (
    EmptyReleaseNotesError,
    NegativeReleaseVersionError,
    ReleaseNotesTooLongError,
)
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
    ReleaseNotes,
)


class TestCourseReleaseVersion:
    def test_initial_baseline(self) -> None:
        v = CourseReleaseVersion.initial()
        assert (v.major, v.minor, v.patch) == (0, 0, 0)

    def test_bumped_patch(self) -> None:
        v = CourseReleaseVersion(1, 2, 3).bumped(CourseReleaseKind.PATCH)
        assert (v.major, v.minor, v.patch) == (1, 2, 4)

    def test_bumped_minor_resets_patch(self) -> None:
        v = CourseReleaseVersion(1, 2, 3).bumped(CourseReleaseKind.MINOR)
        assert (v.major, v.minor, v.patch) == (1, 3, 0)

    def test_bumped_major_resets_minor_and_patch(self) -> None:
        v = CourseReleaseVersion(1, 2, 3).bumped(CourseReleaseKind.MAJOR)
        assert (v.major, v.minor, v.patch) == (2, 0, 0)

    def test_first_patch_from_baseline(self) -> None:
        v = CourseReleaseVersion.initial().bumped(CourseReleaseKind.PATCH)
        assert (v.major, v.minor, v.patch) == (0, 0, 1)

    def test_first_minor_from_baseline(self) -> None:
        v = CourseReleaseVersion.initial().bumped(CourseReleaseKind.MINOR)
        assert (v.major, v.minor, v.patch) == (0, 1, 0)

    def test_first_major_from_baseline(self) -> None:
        v = CourseReleaseVersion.initial().bumped(CourseReleaseKind.MAJOR)
        assert (v.major, v.minor, v.patch) == (1, 0, 0)

    def test_rejects_negative_components(self) -> None:
        with pytest.raises(NegativeReleaseVersionError):
            CourseReleaseVersion(-1, 0, 0)
        with pytest.raises(NegativeReleaseVersionError):
            CourseReleaseVersion(0, -1, 0)
        with pytest.raises(NegativeReleaseVersionError):
            CourseReleaseVersion(0, 0, -1)


class TestReleaseNotes:
    def test_accepts_valid(self) -> None:
        assert ReleaseNotes("Hello").value == "Hello"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyReleaseNotesError):
            ReleaseNotes("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ReleaseNotesTooLongError):
            ReleaseNotes("x" * (RELEASE_NOTES_MAX_LEN + 1))

    def test_of_optional_returns_none_for_none(self) -> None:
        assert ReleaseNotes.of_optional(None) is None
