from typing import Protocol

from learnic.entities.course_block.ids import CollageItemID, LessonBlockID
from learnic.entities.course_block.models import (
    CodeBlock,
    CollageItem,
    FileBlock,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    MultiChoiceBlock,
    PhotoCollageBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
    VideoFileBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.file.ids import FileID


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

    async def add_file(self, block: FileBlock) -> None: ...

    async def update_file(self, block: FileBlock) -> None: ...

    async def add_video_file(self, block: VideoFileBlock) -> None: ...

    async def update_video_file(self, block: VideoFileBlock) -> None: ...

    async def add_photo_collage(self, block: PhotoCollageBlock) -> None:
        """Insert the parent block row plus one row per ``CollageItem``.

        Items are persisted via ``photo_collage_items`` rows in the
        same call so callers don't have to wire two gateway methods
        for one entity create. ``position`` is assigned from the
        order of ``block.items``.
        """
        ...

    async def add_photo_collage_item(
        self,
        block: PhotoCollageBlock,
        item: CollageItem,
    ) -> None:
        """Insert one item row into the collage's items child table.

        ``item.position`` is implicit — the row is appended at
        ``len(block.items) - 1`` so callers can compute the value
        directly from the post-mutation block state. The parent
        block's ``updated_at`` is bumped in the same call so live
        subscribers see a change on their next refetch.
        """
        ...

    async def remove_photo_collage_item(
        self,
        block: PhotoCollageBlock,
        item_id: CollageItemID,
    ) -> None:
        """Drop one item row by id and re-pack ``position`` on survivors.

        ``block`` is the post-mutation entity — the gateway uses its
        ``items`` order to rewrite ``position`` on the surviving rows
        so the ``UNIQUE(block_id, position)`` invariant holds. The
        parent block's ``updated_at`` is bumped.
        """
        ...

    async def reorder_photo_collage_items(
        self,
        block: PhotoCollageBlock,
    ) -> None:
        """Rewrite ``position`` on every items row from ``block.items``."""
        ...

    async def update_photo_collage_item_caption(
        self,
        block: PhotoCollageBlock,
        item_id: CollageItemID,
    ) -> None:
        """Patch one item's ``caption`` column from ``block.items``."""
        ...

    async def update_photo_collage_title(
        self,
        block: PhotoCollageBlock,
    ) -> None:
        """Patch only the ``title`` column on the parent collage row."""
        ...

    async def delete(self, oid: LessonBlockID) -> None: ...

    async def remove_file_from_collages(
        self,
        file_id: FileID,
    ) -> None:
        """Null out every ``photo_collage_items.file_id`` that points at
        ``file_id`` so the SET NULL semantics are visible to live
        subscribers immediately, without waiting for the file row's
        own CASCADE/SET NULL chain to fire.

        Used by the S3-purge worker as part of hard-delete cleanup:
        ``file_blocks`` / ``video_file_blocks`` are CASCADE'd through
        the FK and disappear together with the file, but a photo
        collage represents a *gallery* and surviving items are
        independent — losing one to quota enforcement does not
        invalidate the others. So this method only excises the
        offending item from each affected collage; the collage block
        itself stays in place even if every item ends up file-less
        (the author can clean up the placeholder rows on their own
        time).

        Idempotent — when no collage references the file, no
        rows are touched.
        """
        ...

    async def reorder(
        self,
        lesson_id: CourseLessonID,
        ordered_ids: list[LessonBlockID],
    ) -> None:
        """Atomic full-reorder of all blocks within a lesson."""
        ...
