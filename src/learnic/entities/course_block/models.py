import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.value_objects import (
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


LessonBlock = HtmlBlock | KatexBlock | RutubeVideoBlock
