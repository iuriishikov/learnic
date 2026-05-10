"""Adapters for course releases — Gateway, Snapshotter, Reader.

The Gateway and entity-mapping path is conventional imperative
SA. The Snapshotter is Core-only — it copies draft rows into the
snapshot mirror tables in three batched INSERT phases (modules →
lessons → blocks + per-type child tables), generating fresh
UUIDs in Python so the new rows can FK to the new release row
without depending on draft ids that may later be deleted.

The Reader walks the snapshot tables in the same Core style as
:class:`CourseContentReaderAlchemy` for the draft side.
"""

import uuid
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_content import (
    CodeBlockView,
    CodeTabView,
    HtmlBlockView,
    KatexBlockView,
    LessonBlockView,
    RutubeVideoBlockView,
)
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
    CourseReleaseGateway,
    CourseReleaseReader,
    CourseReleaseSnapshotter,
    CourseReleaseSummaryView,
    ReleaseLessonView,
    ReleaseModuleView,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.course_block import (
    code_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    rutube_video_blocks_table,
)
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    course_modules_table,
)
from learnic.infrastructure.persistence.models.course_release import (
    course_release_blocks_table,
    course_release_code_blocks_table,
    course_release_html_blocks_table,
    course_release_katex_blocks_table,
    course_release_lessons_table,
    course_release_modules_table,
    course_release_rutube_video_blocks_table,
    course_releases_table,
)


# ============================== gateway ============================== #


class CourseReleaseMapperAlchemy(CourseReleaseGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: CourseReleaseID,
    ) -> CourseRelease | None:
        stmt = sa.select(CourseRelease).where(
            course_releases_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def latest_for_product(
        self,
        product_id: ProductID,
    ) -> CourseRelease | None:
        stmt = (
            sa.select(CourseRelease)
            .where(course_releases_table.c.product_id == product_id)
            .order_by(course_releases_table.c.ordinal.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


# ============================== snapshotter ============================== #


class CourseReleaseSnapshotterAlchemy(CourseReleaseSnapshotter):
    """Copies draft content into release-snapshot tables.

    Three SELECT-then-INSERT phases (modules / lessons / blocks).
    Fresh UUIDs are generated in Python; old → new id mappings are
    held in dicts to fix up child references. Uses ``executemany``
    for the bulk INSERTs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def snapshot(self, release: CourseRelease) -> None:
        module_map = await self._snapshot_modules(release)
        lesson_map = await self._snapshot_lessons(release, module_map)
        await self._snapshot_blocks(release, lesson_map)

    async def _snapshot_modules(
        self,
        release: CourseRelease,
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    course_modules_table.c.oid,
                    course_modules_table.c.title,
                    course_modules_table.c.description,
                    course_modules_table.c.position,
                ).where(course_modules_table.c.product_id == release.product_id),
            )
        ).all()
        if not rows:
            return {}

        mapping: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}
        values = [
            {
                "oid": mapping[row.oid],
                "release_id": release.oid,
                "source_module_id": row.oid,
                "title": row.title,
                "description": row.description,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(course_release_modules_table),
            values,
        )
        return mapping

    async def _snapshot_lessons(
        self,
        release: CourseRelease,
        module_map: dict[uuid.UUID, uuid.UUID],
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    course_lessons_table.c.oid,
                    course_lessons_table.c.module_id,
                    course_lessons_table.c.title,
                    course_lessons_table.c.position,
                ).where(course_lessons_table.c.product_id == release.product_id),
            )
        ).all()
        if not rows:
            return {}

        mapping: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}
        values = [
            {
                "oid": mapping[row.oid],
                "release_id": release.oid,
                "release_module_id": module_map[row.module_id],
                "source_lesson_id": row.oid,
                "title": row.title,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(course_release_lessons_table),
            values,
        )
        return mapping

    async def _snapshot_blocks(
        self,
        release: CourseRelease,
        lesson_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        rows = (
            await self._session.execute(
                sa.select(
                    lesson_blocks_table.c.oid,
                    lesson_blocks_table.c.lesson_id,
                    lesson_blocks_table.c.type,
                    lesson_blocks_table.c.position,
                    html_blocks_table.c.html,
                    katex_blocks_table.c.source,
                    rutube_video_blocks_table.c.external_id.label(
                        "rutube_external_id",
                    ),
                    rutube_video_blocks_table.c.title.label("rutube_title"),
                    code_blocks_table.c.tabs.label("code_tabs"),
                )
                .select_from(
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
                    )
                    .outerjoin(
                        code_blocks_table,
                        lesson_blocks_table.c.oid == code_blocks_table.c.oid,
                    ),
                )
                .where(lesson_blocks_table.c.product_id == release.product_id),
            )
        ).all()
        if not rows:
            return

        block_map: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}

        parent_values: list[dict[str, Any]] = [
            {
                "oid": block_map[row.oid],
                "release_id": release.oid,
                "release_lesson_id": lesson_map[row.lesson_id],
                "source_block_id": row.oid,
                "type": row.type.value if hasattr(row.type, "value") else row.type,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(course_release_blocks_table),
            parent_values,
        )

        html_values: list[dict[str, Any]] = []
        katex_values: list[dict[str, Any]] = []
        rutube_values: list[dict[str, Any]] = []
        code_values: list[dict[str, Any]] = []
        for row in rows:
            new_oid = block_map[row.oid]
            block_type = (
                row.type if isinstance(row.type, BlockType) else BlockType(row.type)
            )
            if block_type is BlockType.HTML:
                html_values.append({"oid": new_oid, "html": row.html})
            elif block_type is BlockType.KATEX:
                katex_values.append({"oid": new_oid, "source": row.source})
            elif block_type is BlockType.CODE:
                code_values.append(
                    {
                        "oid": new_oid,
                        # Snapshots take the JSONB tabs payload as-is —
                        # release content is immutable so a deep copy
                        # isn't required (psycopg/asyncpg encodes the
                        # dict to JSON on insert independently per row).
                        "tabs": row.code_tabs,
                    },
                )
            else:  # RUTUBE_VIDEO
                rutube_values.append(
                    {
                        "oid": new_oid,
                        "external_id": row.rutube_external_id,
                        "title": row.rutube_title,
                    },
                )

        if html_values:
            await self._session.execute(
                sa.insert(course_release_html_blocks_table),
                html_values,
            )
        if katex_values:
            await self._session.execute(
                sa.insert(course_release_katex_blocks_table),
                katex_values,
            )
        if rutube_values:
            await self._session.execute(
                sa.insert(course_release_rutube_video_blocks_table),
                rutube_values,
            )
        if code_values:
            await self._session.execute(
                sa.insert(course_release_code_blocks_table),
                code_values,
            )


# ============================== reader ============================== #


def _row_to_block_view(row: sa.Row[Any]) -> LessonBlockView:
    block_type = row.type if isinstance(row.type, BlockType) else BlockType(row.type)
    if block_type is BlockType.HTML:
        return HtmlBlockView(
            type=BlockType.HTML,
            oid=LessonBlockID(row.oid),
            position=row.position,
            html=row.html,
        )
    if block_type is BlockType.KATEX:
        return KatexBlockView(
            type=BlockType.KATEX,
            oid=LessonBlockID(row.oid),
            position=row.position,
            source=row.source,
        )
    if block_type is BlockType.CODE:
        return CodeBlockView(
            type=BlockType.CODE,
            oid=LessonBlockID(row.oid),
            position=row.position,
            tabs=[
                CodeTabView(
                    label=item["label"],
                    source=item["source"],
                    language=item["language"],
                )
                for item in row.code_tabs
            ],
        )
    return RutubeVideoBlockView(
        type=BlockType.RUTUBE_VIDEO,
        oid=LessonBlockID(row.oid),
        position=row.position,
        external_id=row.rutube_external_id,
        title=row.rutube_title,
    )


class CourseReleaseReaderAlchemy(CourseReleaseReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def list_for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseReleaseSummaryView]:
        stmt = (
            sa.select(
                course_releases_table.c.oid,
                course_releases_table.c.ordinal,
                course_releases_table.c.major,
                course_releases_table.c.minor,
                course_releases_table.c.patch,
                course_releases_table.c.kind,
                course_releases_table.c.notes,
                course_releases_table.c.released_at,
                course_releases_table.c.released_by,
            )
            .where(course_releases_table.c.product_id == product_id)
            .order_by(course_releases_table.c.ordinal.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            CourseReleaseSummaryView(
                oid=CourseReleaseID(row.oid),
                ordinal=row.ordinal,
                major=row.major,
                minor=row.minor,
                patch=row.patch,
                kind=CourseReleaseKind(row.kind),
                notes=row.notes,
                released_at=row.released_at,
                released_by=UserID(row.released_by),
            )
            for row in rows
        ]

    @override
    async def get_content(
        self,
        release_id: CourseReleaseID,
    ) -> CourseReleaseContentView | None:
        meta_row = (
            await self._session.execute(
                sa.select(
                    course_releases_table.c.oid,
                    course_releases_table.c.product_id,
                    course_releases_table.c.ordinal,
                    course_releases_table.c.major,
                    course_releases_table.c.minor,
                    course_releases_table.c.patch,
                    course_releases_table.c.kind,
                    course_releases_table.c.notes,
                    course_releases_table.c.released_at,
                ).where(course_releases_table.c.oid == release_id),
            )
        ).one_or_none()
        if meta_row is None:
            return None

        modules_rows = (
            await self._session.execute(
                sa.select(
                    course_release_modules_table.c.oid,
                    course_release_modules_table.c.title,
                    course_release_modules_table.c.description,
                    course_release_modules_table.c.position,
                )
                .where(course_release_modules_table.c.release_id == release_id)
                .order_by(course_release_modules_table.c.position.asc()),
            )
        ).all()

        lessons_rows = (
            await self._session.execute(
                sa.select(
                    course_release_lessons_table.c.oid,
                    course_release_lessons_table.c.release_module_id,
                    course_release_lessons_table.c.title,
                    course_release_lessons_table.c.position,
                )
                .where(course_release_lessons_table.c.release_id == release_id)
                .order_by(
                    course_release_lessons_table.c.release_module_id.asc(),
                    course_release_lessons_table.c.position.asc(),
                ),
            )
        ).all()

        blocks_rows = (
            await self._session.execute(
                sa.select(
                    course_release_blocks_table.c.oid,
                    course_release_blocks_table.c.release_lesson_id,
                    course_release_blocks_table.c.type,
                    course_release_blocks_table.c.position,
                    course_release_html_blocks_table.c.html,
                    course_release_katex_blocks_table.c.source,
                    course_release_rutube_video_blocks_table.c.external_id.label(
                        "rutube_external_id",
                    ),
                    course_release_rutube_video_blocks_table.c.title.label(
                        "rutube_title",
                    ),
                    course_release_code_blocks_table.c.tabs.label(
                        "code_tabs",
                    ),
                )
                .select_from(
                    course_release_blocks_table.outerjoin(
                        course_release_html_blocks_table,
                        course_release_blocks_table.c.oid
                        == course_release_html_blocks_table.c.oid,
                    )
                    .outerjoin(
                        course_release_katex_blocks_table,
                        course_release_blocks_table.c.oid
                        == course_release_katex_blocks_table.c.oid,
                    )
                    .outerjoin(
                        course_release_rutube_video_blocks_table,
                        course_release_blocks_table.c.oid
                        == course_release_rutube_video_blocks_table.c.oid,
                    )
                    .outerjoin(
                        course_release_code_blocks_table,
                        course_release_blocks_table.c.oid
                        == course_release_code_blocks_table.c.oid,
                    ),
                )
                .where(course_release_blocks_table.c.release_id == release_id)
                .order_by(
                    course_release_blocks_table.c.release_lesson_id.asc(),
                    course_release_blocks_table.c.position.asc(),
                ),
            )
        ).all()

        blocks_by_lesson: dict[uuid.UUID, list[LessonBlockView]] = {}
        for row in blocks_rows:
            blocks_by_lesson.setdefault(
                row.release_lesson_id,
                [],
            ).append(_row_to_block_view(row))

        lessons_by_module: dict[uuid.UUID, list[ReleaseLessonView]] = {}
        for row in lessons_rows:
            lessons_by_module.setdefault(
                row.release_module_id,
                [],
            ).append(
                ReleaseLessonView(
                    oid=CourseLessonID(row.oid),
                    title=row.title,
                    position=row.position,
                    blocks=blocks_by_lesson.get(row.oid, []),
                ),
            )

        modules: list[ReleaseModuleView] = [
            ReleaseModuleView(
                oid=CourseModuleID(row.oid),
                title=row.title,
                description=row.description,
                position=row.position,
                lessons=lessons_by_module.get(row.oid, []),
            )
            for row in modules_rows
        ]

        return CourseReleaseContentView(
            release_id=CourseReleaseID(meta_row.oid),
            product_id=ProductID(meta_row.product_id),
            ordinal=meta_row.ordinal,
            major=meta_row.major,
            minor=meta_row.minor,
            patch=meta_row.patch,
            kind=CourseReleaseKind(meta_row.kind),
            notes=meta_row.notes,
            released_at=meta_row.released_at,
            modules=modules,
        )
