from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.persistence.note_content import (
    LessonBlockView,
)
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import LessonBlock
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


# ---------- gateway (write side) ----------


class NoteReleaseGateway(Protocol):
    """Write-side lookups and persistence for :class:`NoteRelease`."""

    async def with_id(
        self,
        oid: NoteReleaseID,
    ) -> NoteRelease | None: ...

    async def latest_for_product(
        self,
        product_id: ProductID,
    ) -> NoteRelease | None:
        """Return the highest-``ordinal`` release of the product or ``None``."""
        ...

    async def count_for_product(self, product_id: ProductID) -> int:
        """Return how many releases the product already has.

        Used by ``CreateNoteReleaseCommandHandler`` to enforce
        :data:`NOTE_RELEASE_LIMIT` — every release deep-copies the
        whole draft tree into the snapshot mirror tables, so the count
        is an abuse guard on storage blast-radius, not a domain
        invariant.
        """
        ...


class NoteReleaseBlockGateway(Protocol):
    """Read-side lookup for a single block inside a release snapshot.

    Used by check/reveal handlers — the student-facing flow needs
    a one-off load of an interactive block (without walking the
    whole content tree). Returns the same ``LessonBlock`` domain
    entity as the draft-side gateway so business logic (e.g.
    ``block.check(payload)``) is type-agnostic about where the
    block came from.

    ``product_id`` on the returned entity is the **product** the
    release belongs to — that is what the handler uses to verify
    the caller's enrollment. ``lesson_id`` is the release-side
    lesson id and is not consumed by the check flow.
    """

    async def with_id(
        self,
        oid: LessonBlockID,
    ) -> LessonBlock | None: ...


class NoteReleaseSnapshotter(Protocol):
    """Atomic copy of draft content into release-snapshot tables.

    Reads ``note_modules`` / ``note_lessons`` / ``lesson_blocks``
    + child tables for ``release.product_id`` and writes mirror rows
    into ``note_release_*`` tables, generating fresh UUIDs and
    pinning every row to ``release.oid``. The release row itself
    must be inserted by the handler beforehand (this Protocol is
    pure copy).
    """

    async def snapshot(self, release: NoteRelease) -> None: ...


# ---------- reader (read side) ----------


@dataclass(slots=True, frozen=True)
class NoteReleaseSummaryView:
    """Lightweight projection for ``GET /products/{id}/releases``."""

    oid: NoteReleaseID
    ordinal: int
    major: int
    minor: int
    patch: int
    kind: NoteReleaseKind
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

    oid: NoteLessonID
    title: str
    position: int
    blocks: list[LessonBlockView]


@dataclass(slots=True, frozen=True)
class ReleaseModuleView:
    """Module projection inside a release content tree."""

    oid: NoteModuleID
    title: str
    description: str | None
    position: int
    lessons: list[ReleaseLessonView]


@dataclass(slots=True, frozen=True)
class NoteReleaseContentView:
    """Full content tree of a specific release."""

    release_id: NoteReleaseID
    product_id: ProductID
    ordinal: int
    major: int
    minor: int
    patch: int
    kind: NoteReleaseKind
    notes: str | None
    released_at: datetime
    modules: list[ReleaseModuleView]


class NoteReleaseReader(Protocol):
    """Read-side queries returning release projections."""

    async def list_for_product(
        self,
        product_id: ProductID,
    ) -> list[NoteReleaseSummaryView]:
        """Return all releases of a product, newest first (descending ordinal)."""
        ...

    async def get_content(
        self,
        release_id: NoteReleaseID,
    ) -> NoteReleaseContentView | None: ...
