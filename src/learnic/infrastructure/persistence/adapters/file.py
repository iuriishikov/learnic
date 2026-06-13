from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
    FileMeta,
)
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.note_lesson import (
    note_lessons_table,
)
from learnic.infrastructure.persistence.models.note_block import (
    file_blocks_table,
    lesson_blocks_table,
    photo_collage_items_table,
    video_file_blocks_table,
)
from learnic.infrastructure.persistence.models.note_release import (
    note_release_file_blocks_table,
    note_release_photo_collage_blocks_table,
    note_release_video_file_blocks_table,
)
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.product import products_table


class FilesMapperAlchemy(FilesGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: FileID) -> File | None:
        stmt = sa.select(File).where(files_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def is_referenced_by_release(self, oid: FileID) -> bool:
        # Only published-release snapshots pin a file against deletion
        # (they share the draft's exact blob). Two mirrors carry an FK
        # ``file_id``; the collage mirror keeps items in a JSONB array
        # of ``{"oid", "file_id", "caption"}`` dicts, matched with a
        # ``@>`` containment probe rather than an FK compare.
        collage_probe = [{"file_id": str(oid)}]
        pinned = sa.or_(
            sa.select(sa.literal(1))
            .where(note_release_file_blocks_table.c.file_id == oid)
            .exists(),
            sa.select(sa.literal(1))
            .where(note_release_video_file_blocks_table.c.file_id == oid)
            .exists(),
            sa.select(sa.literal(1))
            .where(
                # Subscript access: a column literally named ``items``
                # collides with ``ColumnCollection.items()`` under
                # attribute access (typing + runtime), so index it.
                note_release_photo_collage_blocks_table.c["items"].contains(
                    collage_probe,
                ),
            )
            .exists(),
        )
        result = await self._session.execute(sa.select(pinned))
        return bool(result.scalar_one())

    @override
    async def delete(self, oid: FileID) -> None:
        await self._session.execute(
            sa.delete(files_table).where(files_table.c.oid == oid),
        )


class FilesReaderAlchemy(FilesReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: FileID) -> FileMeta | None:
        stmt = sa.select(
            files_table.c.oid,
            files_table.c.storage_name,
            files_table.c.bucket,
            files_table.c.content_type,
            files_table.c.size_bytes,
        ).where(
            files_table.c.oid == oid,
            files_table.c.deleted_at.is_(None),
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return FileMeta(
            oid=FileID(row.oid),
            storage_name=row.storage_name,
            bucket=row.bucket,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
        )

    @override
    async def with_ids(self, oids: list[FileID]) -> dict[FileID, FileMeta]:
        if not oids:
            return {}
        stmt = sa.select(
            files_table.c.oid,
            files_table.c.storage_name,
            files_table.c.bucket,
            files_table.c.content_type,
            files_table.c.size_bytes,
        ).where(
            files_table.c.oid.in_(oids),
            files_table.c.deleted_at.is_(None),
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            FileID(row.oid): FileMeta(
                oid=FileID(row.oid),
                storage_name=row.storage_name,
                bucket=row.bucket,
                content_type=row.content_type,
                size_bytes=row.size_bytes,
            )
            for row in rows
        }

    @override
    async def file_ids_for_product(
        self,
        product_id: ProductID,
    ) -> list[FileID]:
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        # Collage items now live in a child table — straight join.
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        cover_path = (
            sa.select(products_table.c.cover_file_id.label("file_id"))
            .where(
                products_table.c.oid == product_id,
                products_table.c.cover_file_id.is_not(None),
            )
        )
        union = sa.union_all(
            file_path,
            video_path,
            collage_path,
            cover_path,
        ).subquery("product_file_ids")
        stmt = (
            sa.select(union.c.file_id)
            .distinct()
            .join_from(
                union,
                files_table,
                files_table.c.oid == union.c.file_id,
            )
            .where(files_table.c.deleted_at.is_(None))
        )
        rows = (await self._session.execute(stmt)).all()
        return [FileID(row.file_id) for row in rows]

    @override
    async def file_ids_for_lesson(
        self,
        lesson_id: NoteLessonID,
    ) -> list[FileID]:
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.lesson_id == lesson_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.lesson_id == lesson_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ),
            )
            .where(
                lesson_blocks_table.c.lesson_id == lesson_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        union = sa.union_all(
            file_path,
            video_path,
            collage_path,
        ).subquery("lesson_file_ids")
        stmt = (
            sa.select(union.c.file_id)
            .distinct()
            .join_from(
                union,
                files_table,
                files_table.c.oid == union.c.file_id,
            )
            .where(files_table.c.deleted_at.is_(None))
        )
        rows = (await self._session.execute(stmt)).all()
        return [FileID(row.file_id) for row in rows]

    @override
    async def file_ids_for_module(
        self,
        module_id: NoteModuleID,
    ) -> list[FileID]:
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ).join(
                    note_lessons_table,
                    note_lessons_table.c.oid
                    == lesson_blocks_table.c.lesson_id,
                ),
            )
            .where(
                note_lessons_table.c.module_id == module_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ).join(
                    note_lessons_table,
                    note_lessons_table.c.oid
                    == lesson_blocks_table.c.lesson_id,
                ),
            )
            .where(
                note_lessons_table.c.module_id == module_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ).join(
                    note_lessons_table,
                    note_lessons_table.c.oid
                    == lesson_blocks_table.c.lesson_id,
                ),
            )
            .where(
                note_lessons_table.c.module_id == module_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        union = sa.union_all(
            file_path,
            video_path,
            collage_path,
        ).subquery("module_file_ids")
        stmt = (
            sa.select(union.c.file_id)
            .distinct()
            .join_from(
                union,
                files_table,
                files_table.c.oid == union.c.file_id,
            )
            .where(files_table.c.deleted_at.is_(None))
        )
        rows = (await self._session.execute(stmt)).all()
        return [FileID(row.file_id) for row in rows]
