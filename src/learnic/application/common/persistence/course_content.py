from dataclasses import dataclass
from typing import Literal, Protocol

from learnic.application.common.persistence.file import FileView
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class HtmlBlockView:
    """Read-side projection of an HTML lesson block."""

    type: Literal[BlockType.HTML]
    oid: LessonBlockID
    position: int
    html: str


@dataclass(slots=True, frozen=True)
class KatexBlockView:
    """Read-side projection of a LaTeX lesson block."""

    type: Literal[BlockType.KATEX]
    oid: LessonBlockID
    position: int
    source: str


@dataclass(slots=True, frozen=True)
class RutubeVideoBlockView:
    """Read-side projection of a Rutube-embed lesson block."""

    type: Literal[BlockType.RUTUBE_VIDEO]
    oid: LessonBlockID
    position: int
    external_id: str
    title: str | None


@dataclass(slots=True, frozen=True)
class CodeTabView:
    """Read-side projection of a single tab inside a code block."""

    label: str
    source: str
    language: str


@dataclass(slots=True, frozen=True)
class CodeBlockView:
    """Read-side projection of a source-code lesson block.

    A code block always has at least one tab; multi-tab blocks
    carry variant snippets (e.g. npm / pnpm / yarn).
    """

    type: Literal[BlockType.CODE]
    oid: LessonBlockID
    position: int
    tabs: list[CodeTabView]


@dataclass(slots=True, frozen=True)
class ChoiceOptionView:
    """One option inside a choice block, as projected to the read side.

    Plain ``(oid, label)`` — UUIDs are kept as strings here because
    this view layer crosses to JSON without further encoding.
    """

    oid: str
    label: str


@dataclass(slots=True, frozen=True)
class SingleChoiceBlockView:
    """Authoring-side projection of a single-choice answer block.

    Carries the ``correct_option_id`` — fine for the authoring tree
    (the author needs to see what they configured). The public
    student-facing view drops it; see ``presentation/http/...``
    for the HTTP-boundary stripping.
    """

    type: Literal[BlockType.SINGLE_CHOICE]
    oid: LessonBlockID
    position: int
    options: list[ChoiceOptionView]
    correct_option_id: str


@dataclass(slots=True, frozen=True)
class MultiChoiceBlockView:
    """Authoring-side projection of a multi-choice answer block."""

    type: Literal[BlockType.MULTI_CHOICE]
    oid: LessonBlockID
    position: int
    options: list[ChoiceOptionView]
    correct_option_ids: list[str]


@dataclass(slots=True, frozen=True)
class TextInputBlockView:
    """Authoring-side projection of a text-input answer block.

    Carries the ``accepted_answers`` — same authoring rationale as
    the choice views; the public student-facing view drops the list.
    """

    type: Literal[BlockType.TEXT_INPUT]
    oid: LessonBlockID
    position: int
    accepted_answers: list[str]
    case_sensitive: bool
    trim_whitespace: bool


@dataclass(slots=True, frozen=True)
class FileBlockView:
    """Read-side projection of a generic-file lesson block.

    ``file`` is nullable so a block that outlived its backing file
    degrades to a missing-file placeholder rather than disappearing.
    Same nullability rationale on the entity side. When present, the
    nested :class:`FileView` already carries a short-lived presigned
    URL — the SPA renders it directly with no follow-up endpoint.
    """

    type: Literal[BlockType.FILE]
    oid: LessonBlockID
    position: int
    file: FileView | None
    title: str | None


@dataclass(slots=True, frozen=True)
class VideoFileBlockView:
    """Read-side projection of an uploaded-video lesson block.

    Sibling of :class:`RutubeVideoBlockView` — same playback intent,
    different provider (project-hosted bytes vs Rutube embed).
    ``file`` carries a resolved :class:`FileView` with presigned URL.
    """

    type: Literal[BlockType.VIDEO_FILE]
    oid: LessonBlockID
    position: int
    file: FileView | None
    title: str | None


@dataclass(slots=True, frozen=True)
class CollageItemView:
    """One photo inside a :class:`PhotoCollageBlockView`.

    ``oid`` is the stable item identity used by the granular
    add/remove/reorder/caption endpoints on the draft side. The
    release-side reader carries the same field — items in the JSONB
    snapshot copy their draft id verbatim so URL bookmarks in
    release-time discussion threads remain meaningful.
    ``file`` is nullable for the same reason as the block-level FK:
    a deleted backing file leaves the item as a placeholder.
    """

    oid: str
    file: FileView | None
    caption: str | None


@dataclass(slots=True, frozen=True)
class PhotoCollageBlockView:
    """Read-side projection of a photo-collage lesson block."""

    type: Literal[BlockType.PHOTO_COLLAGE]
    oid: LessonBlockID
    position: int
    items: list[CollageItemView]
    title: str | None


LessonBlockView = (
    HtmlBlockView
    | KatexBlockView
    | RutubeVideoBlockView
    | CodeBlockView
    | SingleChoiceBlockView
    | MultiChoiceBlockView
    | TextInputBlockView
    | FileBlockView
    | VideoFileBlockView
    | PhotoCollageBlockView
)


@dataclass(slots=True, frozen=True)
class DraftLessonView:
    """Read-side projection of a draft lesson inside the tree view."""

    oid: CourseLessonID
    title: str
    position: int
    blocks: list[LessonBlockView]


@dataclass(slots=True, frozen=True)
class DraftModuleView:
    """Read-side projection of a draft module with its lessons."""

    oid: CourseModuleID
    title: str
    description: str | None
    position: int
    lessons: list[DraftLessonView]


@dataclass(slots=True, frozen=True)
class CourseDraftView:
    """Full draft tree of a course product (modules + lessons + blocks)."""

    product_id: ProductID
    modules: list[DraftModuleView]


class CourseContentReader(Protocol):
    """Read-side queries for course content draft and (later) releases."""

    async def get_draft(self, product_id: ProductID) -> CourseDraftView: ...

    async def with_block_id(
        self,
        block_id: LessonBlockID,
    ) -> tuple[ProductID, LessonBlockView] | None:
        """Return ``(product_id, view)`` for a single block, or ``None``.

        The ``product_id`` is the block's denormalised owning product —
        callers need it to scope authorisation (``AuthzTarget.for_product``)
        without an extra DB round-trip up the aggregate tree.

        Args:
            block_id: Target block's id.

        Returns:
            ``(product_id, LessonBlockView)`` when the block exists,
            otherwise ``None``.
        """
        ...
