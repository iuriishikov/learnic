from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.blog_post_block import (
    BlogPostBlockGateway,
)
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.models import (
    BlogHtmlBlock,
    BlogImageBlock,
    BlogPostBlock,
    BlogVideoBlock,
)
from learnic.entities.blog_post_block.value_objects import (
    BlogBlockCaption,
    BlogHtmlContent,
)
from learnic.entities.file.ids import FileID
from learnic.infrastructure.persistence.models.blog_post_block import (
    blog_post_blocks_table,
    blog_post_html_blocks_table,
    blog_post_image_blocks_table,
    blog_post_video_blocks_table,
)


def _block_type(value: Any) -> BlogPostBlockType:  # noqa: ANN401
    return value if isinstance(value, BlogPostBlockType) else BlogPostBlockType(value)


def _optional_caption(value: str | None) -> BlogBlockCaption | None:
    return BlogBlockCaption(value) if value is not None else None


def _select_block_entities() -> sa.Select[Any]:
    """Parent + child columns sufficient to rebuild a block entity."""
    return sa.select(
        blog_post_blocks_table.c.oid,
        blog_post_blocks_table.c.post_id,
        blog_post_blocks_table.c.type,
        blog_post_blocks_table.c.position,
        blog_post_blocks_table.c.created_at,
        blog_post_blocks_table.c.updated_at,
        blog_post_html_blocks_table.c.html.label("html"),
        blog_post_image_blocks_table.c.file_id.label("image_file_id"),
        blog_post_image_blocks_table.c.caption.label("image_caption"),
        blog_post_video_blocks_table.c.file_id.label("video_file_id"),
        blog_post_video_blocks_table.c.title.label("video_title"),
    ).select_from(
        blog_post_blocks_table.outerjoin(
            blog_post_html_blocks_table,
            blog_post_blocks_table.c.oid == blog_post_html_blocks_table.c.oid,
        )
        .outerjoin(
            blog_post_image_blocks_table,
            blog_post_blocks_table.c.oid
            == blog_post_image_blocks_table.c.oid,
        )
        .outerjoin(
            blog_post_video_blocks_table,
            blog_post_blocks_table.c.oid
            == blog_post_video_blocks_table.c.oid,
        ),
    )


def _row_to_entity(row: sa.Row[Any]) -> BlogPostBlock:
    block_type = _block_type(row.type)
    oid = BlogPostBlockID(row.oid)
    post_id = BlogPostID(row.post_id)
    if block_type is BlogPostBlockType.HTML:
        return BlogHtmlBlock(
            oid=oid,
            post_id=post_id,
            html=BlogHtmlContent(row.html),
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    if block_type is BlogPostBlockType.IMAGE:
        return BlogImageBlock(
            oid=oid,
            post_id=post_id,
            file_id=FileID(row.image_file_id),
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
            caption=_optional_caption(row.image_caption),
        )
    return BlogVideoBlock(
        oid=oid,
        post_id=post_id,
        file_id=FileID(row.video_file_id),
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
        title=_optional_caption(row.video_title),
    )


class BlogPostBlockGatewayAlchemy(BlogPostBlockGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def lock_for_post(self, post_id: BlogPostID) -> None:
        await self._session.execute(
            sa.text(
                "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))",
            ),
            {"k": str(post_id)},
        )

    @override
    async def with_id(
        self,
        oid: BlogPostBlockID,
    ) -> BlogPostBlock | None:
        stmt = _select_block_entities().where(
            blog_post_blocks_table.c.oid == oid,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _row_to_entity(row)

    @override
    async def list_for_post(
        self,
        post_id: BlogPostID,
    ) -> list[BlogPostBlock]:
        stmt = (
            _select_block_entities()
            .where(blog_post_blocks_table.c.post_id == post_id)
            .order_by(blog_post_blocks_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_entity(row) for row in rows]

    async def _insert_parent(
        self,
        block: BlogPostBlock,
        block_type: BlogPostBlockType,
    ) -> None:
        await self._session.execute(
            sa.insert(blog_post_blocks_table).values(
                oid=block.oid,
                post_id=block.post_id,
                type=block_type.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )

    async def _touch_parent(self, oid: BlogPostBlockID) -> None:
        await self._session.execute(
            sa.update(blog_post_blocks_table)
            .where(blog_post_blocks_table.c.oid == oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_html(self, block: BlogHtmlBlock) -> None:
        await self._insert_parent(block, BlogPostBlockType.HTML)
        await self._session.execute(
            sa.insert(blog_post_html_blocks_table).values(
                oid=block.oid,
                html=block.html.value,
            ),
        )

    @override
    async def update_html(self, block: BlogHtmlBlock) -> None:
        await self._session.execute(
            sa.update(blog_post_html_blocks_table)
            .where(blog_post_html_blocks_table.c.oid == block.oid)
            .values(html=block.html.value),
        )
        await self._touch_parent(block.oid)

    @override
    async def add_image(self, block: BlogImageBlock) -> None:
        await self._insert_parent(block, BlogPostBlockType.IMAGE)
        await self._session.execute(
            sa.insert(blog_post_image_blocks_table).values(
                oid=block.oid,
                file_id=block.file_id,
                caption=(
                    block.caption.value
                    if block.caption is not None
                    else None
                ),
            ),
        )

    @override
    async def update_image(self, block: BlogImageBlock) -> None:
        await self._session.execute(
            sa.update(blog_post_image_blocks_table)
            .where(blog_post_image_blocks_table.c.oid == block.oid)
            .values(
                file_id=block.file_id,
                caption=(
                    block.caption.value
                    if block.caption is not None
                    else None
                ),
            ),
        )
        await self._touch_parent(block.oid)

    @override
    async def add_video(self, block: BlogVideoBlock) -> None:
        await self._insert_parent(block, BlogPostBlockType.VIDEO)
        await self._session.execute(
            sa.insert(blog_post_video_blocks_table).values(
                oid=block.oid,
                file_id=block.file_id,
                title=(
                    block.title.value if block.title is not None else None
                ),
            ),
        )

    @override
    async def update_video(self, block: BlogVideoBlock) -> None:
        await self._session.execute(
            sa.update(blog_post_video_blocks_table)
            .where(blog_post_video_blocks_table.c.oid == block.oid)
            .values(
                file_id=block.file_id,
                title=(
                    block.title.value if block.title is not None else None
                ),
            ),
        )
        await self._touch_parent(block.oid)

    @override
    async def delete(self, oid: BlogPostBlockID) -> None:
        # Child row cascades via the FK ON DELETE CASCADE.
        await self._session.execute(
            sa.delete(blog_post_blocks_table).where(
                blog_post_blocks_table.c.oid == oid,
            ),
        )

    @override
    async def reorder(
        self,
        post_id: BlogPostID,
        ordered_ids: list[BlogPostBlockID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {
            oid: idx for idx, oid in enumerate(ordered_ids)
        }
        case_expr = sa.case(whens, value=blog_post_blocks_table.c.oid)
        stmt = (
            sa.update(blog_post_blocks_table)
            .where(blog_post_blocks_table.c.post_id == post_id)
            .where(blog_post_blocks_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
