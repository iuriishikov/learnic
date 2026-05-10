import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_block.constants import CODE_BLOCK_MAX_TABS
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.errors import (
    DuplicateCodeTabLabelError,
    EmptyCodeTabsError,
    TooManyCodeTabsError,
)
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.value_objects import (
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.product.ids import ProductID


@dataclass
class HtmlBlock(BaseEntity[LessonBlockID]):
    """A draft HTML-content block inside a lesson.

    ``product_id`` is denormalised from the parent lesson so
    ownership checks read the block alone (no extra JOIN).
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    html: HtmlContent
    position: int
    created_at: datetime
    updated_at: datetime

    @property
    def type(self) -> BlockType:
        return BlockType.HTML

    def update_html(self, new_html: HtmlContent) -> None:
        self.html = new_html

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        html: HtmlContent,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            html=html,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class KatexBlock(BaseEntity[LessonBlockID]):
    """A draft KaTeX-source block inside a lesson.

    Body is KaTeX-flavored math source — a strict subset of LaTeX
    rendered client-side via the KaTeX library. See
    https://katex.org/docs/support_table.html for the supported
    command surface.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    source: KatexSource
    position: int
    created_at: datetime
    updated_at: datetime

    @property
    def type(self) -> BlockType:
        return BlockType.KATEX

    def update_source(self, new_source: KatexSource) -> None:
        self.source = new_source

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        source: KatexSource,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            source=source,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class RutubeVideoBlock(BaseEntity[LessonBlockID]):
    """A draft Rutube-embed block inside a lesson.

    Rutube is the only video provider supported today; if/when
    another provider is needed (YouTube, Vimeo) it will get its
    own block type rather than a generic ``video`` one — embed
    URL templates and id formats diverge enough that a single
    abstraction would lie.

    The embed URL is computed at the presentation layer from
    ``external_id`` as ``https://rutube.ru/play/embed/{id}/``.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    external_id: RutubeVideoID
    position: int
    created_at: datetime
    updated_at: datetime
    title: VideoTitle | None = None

    @property
    def type(self) -> BlockType:
        return BlockType.RUTUBE_VIDEO

    def update_external_id(self, new_id: RutubeVideoID) -> None:
        self.external_id = new_id

    def update_title(self, new_title: VideoTitle | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        external_id: RutubeVideoID,
        position: int,
        title: VideoTitle | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            external_id=external_id,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


@dataclass(frozen=True, slots=True)
class CodeTab:
    """One tab inside a :class:`CodeBlock`.

    A tab is a ``(label, source, language)`` triple. ``label`` is
    visible to the student in the tab strip — empty string is only
    allowed for single-tab blocks (where no strip is rendered).
    Multi-tab blocks must have non-empty unique labels; that
    invariant lives on the parent :class:`CodeBlock` so it can see
    all tabs at once.
    """

    label: CodeTabLabel
    source: CodeSource
    language: CodeLanguage


def _validate_tabs(tabs: list[CodeTab]) -> None:
    """Apply the cross-tab invariants: count + label uniqueness."""
    if not tabs:
        raise EmptyCodeTabsError()
    if len(tabs) > CODE_BLOCK_MAX_TABS:
        raise TooManyCodeTabsError(CODE_BLOCK_MAX_TABS)
    if len(tabs) > 1:
        seen: set[str] = set()
        for tab in tabs:
            if not tab.label.value:
                # Multi-tab blocks need real labels — empty label is
                # only meaningful for the single-tab case.
                raise DuplicateCodeTabLabelError("")
            if tab.label.value in seen:
                raise DuplicateCodeTabLabelError(tab.label.value)
            seen.add(tab.label.value)


@dataclass
class CodeBlock(BaseEntity[LessonBlockID]):
    """A draft source-code block inside a lesson.

    A code block is a non-empty list of tabs (variants). The most
    common case is a single tab — the tab strip is hidden client-
    side, so the block reads as a plain code snippet. Multi-tab
    blocks are for variant snippets like ``npm`` / ``pnpm`` /
    ``yarn``: same intent, different shells.

    ``language`` per tab is bound to :class:`CodeBlockLanguage`;
    sources are preserved verbatim.
    """

    lesson_id: CourseLessonID
    product_id: ProductID
    tabs: list[CodeTab]
    position: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate_tabs(self.tabs)

    @property
    def type(self) -> BlockType:
        return BlockType.CODE

    def replace_tabs(self, new_tabs: list[CodeTab]) -> None:
        _validate_tabs(new_tabs)
        self.tabs = new_tabs

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        lesson_id: CourseLessonID,
        product_id: ProductID,
        tabs: list[CodeTab],
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=LessonBlockID(uuid.uuid4()),
            lesson_id=lesson_id,
            product_id=product_id,
            tabs=tabs,
            position=position,
            created_at=now,
            updated_at=now,
        )


LessonBlock = HtmlBlock | KatexBlock | RutubeVideoBlock | CodeBlock
