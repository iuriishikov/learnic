from typing import Protocol

from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import (
    CodeBlock,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    MultiChoiceBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID


class LessonBlockGateway(Protocol):
    """Write-side gateway for lesson blocks.

    Joined inheritance (parent ``lesson_blocks`` + per-type child
    tables) is awkward in SQLAlchemy imperative mapping, so this
    gateway works through Core: each ``add_*`` / ``update_*``
    method explicitly issues two statements (parent + child) in
    the request transaction.
    """

    async def with_id(
        self,
        oid: LessonBlockID,
    ) -> LessonBlock | None: ...

    async def list_for_lesson(
        self,
        lesson_id: CourseLessonID,
    ) -> list[LessonBlock]:
        """Return all blocks of a lesson, ordered by position ascending."""
        ...

    async def add_html(self, block: HtmlBlock) -> None: ...

    async def update_html(self, block: HtmlBlock) -> None: ...

    async def add_katex(self, block: KatexBlock) -> None: ...

    async def update_katex(self, block: KatexBlock) -> None: ...

    async def add_rutube_video(self, block: RutubeVideoBlock) -> None: ...

    async def update_rutube_video(self, block: RutubeVideoBlock) -> None: ...

    async def add_code(self, block: CodeBlock) -> None: ...

    async def update_code(self, block: CodeBlock) -> None: ...

    async def add_single_choice(self, block: SingleChoiceBlock) -> None: ...

    async def update_single_choice(self, block: SingleChoiceBlock) -> None: ...

    async def add_multi_choice(self, block: MultiChoiceBlock) -> None: ...

    async def update_multi_choice(self, block: MultiChoiceBlock) -> None: ...

    async def add_text_input(self, block: TextInputBlock) -> None: ...

    async def update_text_input(self, block: TextInputBlock) -> None: ...

    async def delete(self, oid: LessonBlockID) -> None: ...

    async def reorder(
        self,
        lesson_id: CourseLessonID,
        ordered_ids: list[LessonBlockID],
    ) -> None:
        """Atomic full-reorder of all blocks within a lesson."""
        ...
