from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.persistence.course_content import (
    LessonBlockView,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


# ---------- gateway (write side) ----------


class CourseReleaseGateway(Protocol):
    """Write-side lookups and persistence for :class:`CourseRelease`."""

    async def with_id(
        self,
        oid: CourseReleaseID,
    ) -> CourseRelease | None: ...

    async def latest_for_product(
        self,
        product_id: ProductID,
    ) -> CourseRelease | None:
        """Return the highest-``ordinal`` release of the product or ``None``."""
        ...


class CourseReleaseSnapshotter(Protocol):
    """Atomic copy of draft content into release-snapshot tables.

    Reads ``course_modules`` / ``course_lessons`` / ``lesson_blocks``
    + child tables for ``release.product_id`` and writes mirror rows
    into ``course_release_*`` tables, generating fresh UUIDs and
    pinning every row to ``release.oid``. The release row itself
    must be inserted by the handler beforehand (this Protocol is
    pure copy).
    """

    async def snapshot(self, release: CourseRelease) -> None: ...


# ---------- reader (read side) ----------


@dataclass(slots=True, frozen=True)
class CourseReleaseSummaryView:
    """Lightweight projection for ``GET /products/{id}/releases``."""

    oid: CourseReleaseID
    ordinal: int
    major: int
    minor: int
    patch: int
    kind: CourseReleaseKind
    notes: str | None
    released_at: datetime
    released_by: UserID


@dataclass(slots=True, frozen=True)
class ReleaseLessonView:
    """Lesson projection inside a release content tree.

    Same shape as ``DraftLessonView`` but with ``LessonBlockView``
    blocks (the discriminated union is shared between draft and
    release reads — block content has the same shape on both sides).
    """

    oid: CourseLessonID
    title: str
    position: int
    blocks: list[LessonBlockView]


@dataclass(slots=True, frozen=True)
class ReleaseModuleView:
    """Module projection inside a release content tree."""

    oid: CourseModuleID
    title: str
    description: str | None
    position: int
    lessons: list[ReleaseLessonView]


@dataclass(slots=True, frozen=True)
class CourseReleaseContentView:
    """Full content tree of a specific release."""

    release_id: CourseReleaseID
    product_id: ProductID
    ordinal: int
    major: int
    minor: int
    patch: int
    kind: CourseReleaseKind
    notes: str | None
    released_at: datetime
    modules: list[ReleaseModuleView]


class CourseReleaseReader(Protocol):
    """Read-side queries returning release projections."""

    async def list_for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseReleaseSummaryView]:
        """Return all releases of a product, newest first (descending ordinal)."""
        ...

    async def get_content(
        self,
        release_id: CourseReleaseID,
    ) -> CourseReleaseContentView | None: ...
