from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import (
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_block.value_objects import (
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.course_block import (
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    rutube_video_blocks_table,
)


def _row_to_block(row: sa.Row[Any]) -> LessonBlock:
    """Hydrate a parent + LEFT JOIN child row into a domain entity.

    The caller's SELECT must include the type-specific columns
    aliased as ``html``, ``source``, ``rutube_external_id``,
    ``rutube_title``. Left joins yield NULL for the other types'
    columns.
    """
    block_type = BlockType(row.type)
    if block_type is BlockType.HTML:
        return HtmlBlock(
            oid=LessonBlockID(row.oid),
            lesson_id=CourseLessonID(row.lesson_id),
            product_id=ProductID(row.product_id),
            html=HtmlContent(row.html),
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    if block_type is BlockType.KATEX:
        return KatexBlock(
            oid=LessonBlockID(row.oid),
            lesson_id=CourseLessonID(row.lesson_id),
            product_id=ProductID(row.product_id),
            source=KatexSource(row.source),
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    return RutubeVideoBlock(
        oid=LessonBlockID(row.oid),
        lesson_id=CourseLessonID(row.lesson_id),
        product_id=ProductID(row.product_id),
        external_id=RutubeVideoID(row.rutube_external_id),
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
        title=(VideoTitle(row.rutube_title) if row.rutube_title is not None else None),
    )


def _select_blocks() -> sa.Select[Any]:
    return sa.select(
        lesson_blocks_table.c.oid,
        lesson_blocks_table.c.lesson_id,
        lesson_blocks_table.c.product_id,
        lesson_blocks_table.c.type,
        lesson_blocks_table.c.position,
        lesson_blocks_table.c.created_at,
        lesson_blocks_table.c.updated_at,
        html_blocks_table.c.html,
        katex_blocks_table.c.source,
        rutube_video_blocks_table.c.external_id.label("rutube_external_id"),
        rutube_video_blocks_table.c.title.label("rutube_title"),
    ).select_from(
        lesson_blocks_table.outerjoin(
            html_blocks_table,
            lesson_blocks_table.c.oid == html_blocks_table.c.oid,
        )
        .outerjoin(
            katex_blocks_table,
            lesson_blocks_table.c.oid == katex_blocks_table.c.oid,
        )
        .outerjoin(
            rutube_video_blocks_table,
            lesson_blocks_table.c.oid == rutube_video_blocks_table.c.oid,
        ),
    )


class LessonBlockGatewayAlchemy(LessonBlockGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: LessonBlockID,
    ) -> LessonBlock | None:
        stmt = _select_blocks().where(lesson_blocks_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _row_to_block(row)

    @override
    async def list_for_lesson(
        self,
        lesson_id: CourseLessonID,
    ) -> list[LessonBlock]:
        stmt = (
            _select_blocks()
            .where(lesson_blocks_table.c.lesson_id == lesson_id)
            .order_by(lesson_blocks_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_block(row) for row in rows]

    @override
    async def add_html(self, block: HtmlBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.HTML.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(html_blocks_table).values(
                oid=block.oid,
                html=block.html.value,
            ),
        )

    @override
    async def update_html(self, block: HtmlBlock) -> None:
        await self._session.execute(
            sa.update(html_blocks_table)
            .where(html_blocks_table.c.oid == block.oid)
            .values(html=block.html.value),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_katex(self, block: KatexBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.KATEX.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(katex_blocks_table).values(
                oid=block.oid,
                source=block.source.value,
            ),
        )

    @override
    async def update_katex(self, block: KatexBlock) -> None:
        await self._session.execute(
            sa.update(katex_blocks_table)
            .where(katex_blocks_table.c.oid == block.oid)
            .values(source=block.source.value),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_rutube_video(self, block: RutubeVideoBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.RUTUBE_VIDEO.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(rutube_video_blocks_table).values(
                oid=block.oid,
                external_id=block.external_id.value,
                title=block.title.value if block.title is not None else None,
            ),
        )

    @override
    async def update_rutube_video(self, block: RutubeVideoBlock) -> None:
        await self._session.execute(
            sa.update(rutube_video_blocks_table)
            .where(rutube_video_blocks_table.c.oid == block.oid)
            .values(
                external_id=block.external_id.value,
                title=block.title.value if block.title is not None else None,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def delete(self, oid: LessonBlockID) -> None:
        # Child rows cascade via FK ON DELETE CASCADE.
        await self._session.execute(
            sa.delete(lesson_blocks_table).where(
                lesson_blocks_table.c.oid == oid,
            ),
        )

    @override
    async def reorder(
        self,
        lesson_id: CourseLessonID,
        ordered_ids: list[LessonBlockID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {oid: idx for idx, oid in enumerate(ordered_ids)}
        case_expr = sa.case(whens, value=lesson_blocks_table.c.oid)
        stmt = (
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.lesson_id == lesson_id)
            .where(lesson_blocks_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
