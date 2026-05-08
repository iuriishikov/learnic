from dataclasses import dataclass
from typing import Literal, Protocol

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


LessonBlockView = HtmlBlockView | KatexBlockView | RutubeVideoBlockView


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
