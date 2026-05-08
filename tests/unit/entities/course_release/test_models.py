import uuid

from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
    ReleaseNotes,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


def _product_id() -> ProductID:
    return ProductID(uuid.uuid4())


def _user_id() -> UserID:
    return UserID(uuid.uuid4())


class TestCreateFirstRelease:
    def test_first_patch_is_v0_0_1(self) -> None:
        r = CourseRelease.create(
            product_id=_product_id(),
            ordinal=1,
            previous_version=None,
            kind=CourseReleaseKind.PATCH,
            released_by=_user_id(),
        )
        assert (
            r.version.major,
            r.version.minor,
            r.version.patch,
        ) == (0, 0, 1)
        assert r.kind is CourseReleaseKind.PATCH
        assert r.notes is None
        assert r.ordinal == 1

    def test_first_minor_is_v0_1_0(self) -> None:
        r = CourseRelease.create(
            product_id=_product_id(),
            ordinal=1,
            previous_version=None,
            kind=CourseReleaseKind.MINOR,
            released_by=_user_id(),
        )
        assert (r.version.major, r.version.minor, r.version.patch) == (0, 1, 0)

    def test_first_major_is_v1_0_0(self) -> None:
        r = CourseRelease.create(
            product_id=_product_id(),
            ordinal=1,
            previous_version=None,
            kind=CourseReleaseKind.MAJOR,
            released_by=_user_id(),
        )
        assert (r.version.major, r.version.minor, r.version.patch) == (1, 0, 0)


class TestCreateNextRelease:
    def test_bumps_from_previous(self) -> None:
        r = CourseRelease.create(
            product_id=_product_id(),
            ordinal=2,
            previous_version=CourseReleaseVersion(1, 0, 0),
            kind=CourseReleaseKind.MINOR,
            released_by=_user_id(),
        )
        assert (r.version.major, r.version.minor, r.version.patch) == (1, 1, 0)

    def test_carries_notes(self) -> None:
        r = CourseRelease.create(
            product_id=_product_id(),
            ordinal=2,
            previous_version=CourseReleaseVersion(0, 0, 1),
            kind=CourseReleaseKind.PATCH,
            released_by=_user_id(),
            notes=ReleaseNotes("Typo fix."),
        )
        assert r.notes is not None
        assert r.notes.value == "Typo fix."
