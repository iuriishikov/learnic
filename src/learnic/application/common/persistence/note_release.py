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

    async def release_id_for_block(
        self,
        oid: LessonBlockID,
    ) -> NoteReleaseID | None:
        """Return the id of the release ``oid`` belongs to, or ``None``.

        Used by check / reveal to confirm the block is part of the
        student's pinned release before grading — without it a student
        pinned to one release could grade/reveal blocks from another
        release of the same product (answer-key leak).
        """
        ...


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


@dataclass(slots=True, frozen=True)
class ReleaseLessonContentView:
    """One release lesson with its block payloads.

    The per-lesson companion of :class:`NoteReleaseContentView` —
    served by ``GET /notes/{note_id}/release-lessons/{lesson_id}``.
    Carries ``release_id`` (the handler compares it against the
    caller's pinned enrollment) and ``product_id`` (for the
    product-level access decision); neither is exposed on the wire.
    """

    oid: NoteLessonID
    release_id: NoteReleaseID
    product_id: ProductID
    title: str
    position: int
    blocks: list[LessonBlockView]


@dataclass(slots=True, frozen=True)
class SchemeLessonView:
    """Lesson projection inside a release scheme tree.

    Structure-only sibling of :class:`ReleaseLessonView` — carries
    no block payloads, only how many blocks the lesson has (the
    catalog page renders a "N materials" label from it).
    """

    oid: NoteLessonID
    title: str
    position: int
    block_count: int


@dataclass(slots=True, frozen=True)
class SchemeModuleView:
    """Module projection inside a release scheme tree."""

    oid: NoteModuleID
    title: str
    description: str | None
    position: int
    lessons: list[SchemeLessonView]


@dataclass(slots=True, frozen=True)
class NoteReleaseSchemeView:
    """Structure-only tree of a specific release.

    Deliberately carries no release header beyond the ids — no
    version triplet, kind, or author-written release ``notes``
    (the changelog can reference gated content). Lessons carry no
    block payloads. This keeps the projection safe to expose
    publicly for invite-only products whose full content is gated.
    """

    release_id: NoteReleaseID
    product_id: ProductID
    modules: list[SchemeModuleView]


@dataclass(slots=True, frozen=True)
class ReleaseSearchMatch:
    """One full-text match inside a release's content tree.

    Returned by :meth:`NoteReleaseReader.search_content`, ranked best
    first. A match is either a content block (``block_id`` set — the
    reader opens the lesson and jumps to that block) or a module /
    lesson title hit (``block_id`` and ``block_type`` ``None`` — the
    reader opens the lesson at the top). ``snippet`` is a
    ``ts_headline`` excerpt with the matched terms wrapped in
    ``<<hl>>…<</hl>>`` markers; the route forwards them verbatim and
    the SPA renders them as highlights (it never injects raw HTML).
    """

    module_id: NoteModuleID
    module_title: str
    lesson_id: NoteLessonID
    lesson_title: str
    block_id: LessonBlockID | None
    block_type: str | None
    snippet: str


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

    async def get_scheme(
        self,
        release_id: NoteReleaseID,
    ) -> NoteReleaseSchemeView | None:
        """Return the structure-only tree (no block payloads)."""
        ...

    async def get_lesson(
        self,
        lesson_id: NoteLessonID,
    ) -> ReleaseLessonContentView | None:
        """Return one release lesson with its blocks, or ``None``."""
        ...

    async def search_content(
        self,
        release_id: NoteReleaseID,
        query: str,
        limit: int,
    ) -> list[ReleaseSearchMatch]:
        """Full-text search a release's content + titles, ranked.

        Scans every block's text (HTML stripped to plain text, KaTeX
        source, code tabs, choice option labels, accepted answers,
        photo captions, media titles, function-graph string leaves)
        plus module titles / descriptions and lesson titles, scoped to
        the one release. Matching is Russian-config full-text
        (stemming) with a ``pg_trgm`` word-similarity fallback for
        typos. Returns at most ``limit`` matches, best rank first.
        """
        ...
