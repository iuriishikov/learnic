from collections.abc import Iterable
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.blog_post import (
    BlogHtmlBlockView,
    BlogImageBlockView,
    BlogPostBlockView,
    BlogPostGateway,
    BlogPostListFilters,
    BlogPostOrder,
    BlogPostReader,
    BlogPostSummaryView,
    BlogPostView,
    BlogVideoBlockView,
)
from learnic.application.common.persistence.file import FileMeta, FileView
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.blog_post.enums import BlogPostStatus
from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post.models import BlogPost
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.file.ids import FileID
from learnic.infrastructure.persistence.models.blog_post import (
    blog_posts_table,
)
from learnic.infrastructure.persistence.models.blog_post_block import (
    blog_post_blocks_table,
    blog_post_html_blocks_table,
    blog_post_image_blocks_table,
    blog_post_video_blocks_table,
)
from learnic.infrastructure.persistence.models.file import files_table


class BlogPostMapperAlchemy(BlogPostGateway):
    """Write-side gateway for the mapped :class:`BlogPost` aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: BlogPostID) -> BlogPost | None:
        stmt = sa.select(BlogPost).where(blog_posts_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def slug_exists(self, slug: str) -> bool:
        stmt = sa.select(
            sa.exists().where(blog_posts_table.c.slug == slug),
        )
        return bool((await self._session.execute(stmt)).scalar())

    @override
    async def delete(self, post: BlogPost) -> None:
        await self._session.delete(post)


def _select_blocks() -> sa.Select[Any]:
    """Parent + LEFT JOIN child columns for every blog-block type."""
    return sa.select(
        blog_post_blocks_table.c.oid,
        blog_post_blocks_table.c.post_id,
        blog_post_blocks_table.c.type,
        blog_post_blocks_table.c.position,
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


def _block_type(value: Any) -> BlogPostBlockType:  # noqa: ANN401
    return value if isinstance(value, BlogPostBlockType) else BlogPostBlockType(value)


def _row_to_block_view(
    row: sa.Row[Any],
    files_by_id: dict[FileID, FileView],
) -> BlogPostBlockView:
    """Hydrate a parent + child row into the matching block view."""
    block_type = _block_type(row.type)
    oid = BlogPostBlockID(row.oid)
    if block_type is BlogPostBlockType.HTML:
        return BlogHtmlBlockView(
            type=BlogPostBlockType.HTML,
            oid=oid,
            position=row.position,
            html=row.html,
        )
    if block_type is BlogPostBlockType.IMAGE:
        file = (
            files_by_id.get(FileID(row.image_file_id))
            if row.image_file_id is not None
            else None
        )
        return BlogImageBlockView(
            type=BlogPostBlockType.IMAGE,
            oid=oid,
            position=row.position,
            file=file,
            caption=row.image_caption,
        )
    file = (
        files_by_id.get(FileID(row.video_file_id))
        if row.video_file_id is not None
        else None
    )
    return BlogVideoBlockView(
        type=BlogPostBlockType.VIDEO,
        oid=oid,
        position=row.position,
        file=file,
        title=row.video_title,
    )


def _post_status(value: Any) -> BlogPostStatus:  # noqa: ANN401
    return value if isinstance(value, BlogPostStatus) else BlogPostStatus(value)


class BlogPostReaderAlchemy(BlogPostReader):
    """Read-side reader; signs presigned URLs for media blocks itself."""

    def __init__(
        self,
        session: AsyncSession,
        file_storage: FileStorage,
    ) -> None:
        self._session: Final = session
        self._file_storage: Final = file_storage

    async def _resolve_files(
        self,
        file_ids: Iterable[FileID],
    ) -> dict[FileID, FileView]:
        ids = list(dict.fromkeys(file_ids))
        if not ids:
            return {}
        stmt = sa.select(
            files_table.c.oid,
            files_table.c.storage_name,
            files_table.c.bucket,
            files_table.c.content_type,
            files_table.c.size_bytes,
        ).where(
            files_table.c.oid.in_(ids),
            files_table.c.deleted_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[FileID, FileView] = {}
        for row in rows:
            meta = FileMeta(
                oid=FileID(row.oid),
                storage_name=row.storage_name,
                bucket=row.bucket,
                content_type=row.content_type,
                size_bytes=row.size_bytes,
            )
            out[FileID(row.oid)] = await FileView.of(
                meta,
                self._file_storage,
            )
        return out

    async def _blocks_for_post(
        self,
        post_id: BlogPostID,
    ) -> list[BlogPostBlockView]:
        stmt = (
            _select_blocks()
            .where(blog_post_blocks_table.c.post_id == post_id)
            .order_by(blog_post_blocks_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        file_ids: list[FileID] = []
        for row in rows:
            if row.image_file_id is not None:
                file_ids.append(FileID(row.image_file_id))
            if row.video_file_id is not None:
                file_ids.append(FileID(row.video_file_id))
        files_by_id = await self._resolve_files(file_ids)
        return [_row_to_block_view(row, files_by_id) for row in rows]

    async def _post_view_from_row(
        self,
        row: sa.Row[Any],
    ) -> BlogPostView:
        blocks = await self._blocks_for_post(BlogPostID(row.oid))
        return BlogPostView(
            oid=BlogPostID(row.oid),
            title=row.title,
            slug=row.slug,
            status=_post_status(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
            published_at=row.published_at,
            blocks=blocks,
        )

    @override
    async def with_id(self, oid: BlogPostID) -> BlogPostView | None:
        stmt = _select_post_columns().where(blog_posts_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return await self._post_view_from_row(row)

    @override
    async def block_with_id(
        self,
        block_id: BlogPostBlockID,
    ) -> BlogPostBlockView | None:
        stmt = _select_blocks().where(
            blog_post_blocks_table.c.oid == block_id,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        file_ids: list[FileID] = []
        if row.image_file_id is not None:
            file_ids.append(FileID(row.image_file_id))
        if row.video_file_id is not None:
            file_ids.append(FileID(row.video_file_id))
        files_by_id = await self._resolve_files(file_ids)
        return _row_to_block_view(row, files_by_id)

    @override
    async def published_with_slug(self, slug: str) -> BlogPostView | None:
        stmt = _select_post_columns().where(
            blog_posts_table.c.slug == slug,
            blog_posts_table.c.status == BlogPostStatus.PUBLISHED,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return await self._post_view_from_row(row)

    @override
    async def list(
        self,
        filters: BlogPostListFilters,
        pagination: Pagination,
        order: BlogPostOrder = BlogPostOrder.CREATED_DESC,
    ) -> list[BlogPostSummaryView]:
        stmt = _select_post_columns()
        if filters.status is not None:
            stmt = stmt.where(blog_posts_table.c.status == filters.status)
        if order is BlogPostOrder.PUBLISHED_DESC:
            # Newest published first; created_at breaks ties (e.g. a
            # backfill that published several posts at once). NULLs
            # last is defensive — the public feed only ever passes
            # this with a PUBLISHED filter, where published_at is set.
            stmt = stmt.order_by(
                blog_posts_table.c.published_at.desc().nullslast(),
                blog_posts_table.c.created_at.desc(),
            )
        else:
            stmt = stmt.order_by(blog_posts_table.c.created_at.desc())
        stmt = stmt.limit(pagination.limit).offset(pagination.offset)
        rows = (await self._session.execute(stmt)).all()
        return [
            BlogPostSummaryView(
                oid=BlogPostID(row.oid),
                title=row.title,
                slug=row.slug,
                status=_post_status(row.status),
                created_at=row.created_at,
                updated_at=row.updated_at,
                published_at=row.published_at,
            )
            for row in rows
        ]

    @override
    async def count(self, filters: BlogPostListFilters) -> int:
        stmt = sa.select(sa.func.count()).select_from(blog_posts_table)
        if filters.status is not None:
            stmt = stmt.where(blog_posts_table.c.status == filters.status)
        return int((await self._session.execute(stmt)).scalar_one())


def _select_post_columns() -> sa.Select[Any]:
    return sa.select(
        blog_posts_table.c.oid,
        blog_posts_table.c.title,
        blog_posts_table.c.slug,
        blog_posts_table.c.status,
        blog_posts_table.c.created_at,
        blog_posts_table.c.updated_at,
        blog_posts_table.c.published_at,
    )
