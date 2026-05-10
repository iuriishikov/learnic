"""Course draft resetter — restores draft tables from a release snapshot.

Mirror of :class:`CourseReleaseSnapshotterAlchemy` (forward draft →
snapshot) but in the reverse direction: snapshot → draft. Used by
``ResetCourseDraftCommandHandler`` to discard in-progress draft
edits and revert to a previously published release.

Operates in three phases (modules → lessons → blocks + child
tables) within the caller's transaction. Generates fresh UUIDs
for every restored row so draft ids stay disjoint from snapshot
ids. Cascading deletes on the draft side fan out from
``course_modules`` (CASCADE → lessons → blocks → child rows), so
a single ``DELETE FROM course_modules WHERE product_id = ?`` is
all we need to wipe the draft.
"""

import uuid
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_draft import (
    CourseDraftResetter,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_release.models import CourseRelease
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
)


class CourseDraftResetterAlchemy(CourseDraftResetter):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def reset(self, release: CourseRelease) -> None:
        # 1. Wipe current draft. CASCADE on FK chains takes care of
        #    course_lessons → lesson_blocks → html/katex/video child rows.
        await self._session.execute(
            sa.delete(course_modules_table).where(
                course_modules_table.c.product_id == release.product_id,
            ),
        )

        # 2. Restore modules from snapshot.
        module_map = await self._restore_modules(release)
        if not module_map:
            return  # release contained no modules; draft stays empty

        # 3. Restore lessons.
        lesson_map = await self._restore_lessons(release, module_map)
        if not lesson_map:
            return

        # 4. Restore blocks + per-type child rows.
        await self._restore_blocks(release, lesson_map)

    async def _restore_modules(
        self,
        release: CourseRelease,
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    course_release_modules_table.c.oid,
                    course_release_modules_table.c.title,
                    course_release_modules_table.c.description,
                    course_release_modules_table.c.position,
                ).where(
                    course_release_modules_table.c.release_id == release.oid,
                ),
            )
        ).all()
        if not rows:
            return {}

        mapping: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}
        values = [
            {
                "oid": mapping[row.oid],
                "product_id": release.product_id,
                "title": row.title,
                "description": row.description,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(course_modules_table),
            values,
        )
        return mapping

    async def _restore_lessons(
        self,
        release: CourseRelease,
        module_map: dict[uuid.UUID, uuid.UUID],
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    course_release_lessons_table.c.oid,
                    course_release_lessons_table.c.release_module_id,
                    course_release_lessons_table.c.title,
                    course_release_lessons_table.c.position,
                ).where(
                    course_release_lessons_table.c.release_id == release.oid,
                ),
            )
        ).all()
        if not rows:
            return {}

        mapping: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}
        values = [
            {
                "oid": mapping[row.oid],
                "module_id": module_map[row.release_module_id],
                "product_id": release.product_id,
                "title": row.title,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(course_lessons_table),
            values,
        )
        return mapping

    async def _restore_blocks(
        self,
        release: CourseRelease,
        lesson_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        rows = (
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
                .where(course_release_blocks_table.c.release_id == release.oid),
            )
        ).all()
        if not rows:
            return

        block_map: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}

        parent_values: list[dict[str, Any]] = [
            {
                "oid": block_map[row.oid],
                "lesson_id": lesson_map[row.release_lesson_id],
                "product_id": release.product_id,
                "type": row.type.value if hasattr(row.type, "value") else row.type,
                "position": row.position,
            }
            for row in rows
        ]
        await self._session.execute(
            sa.insert(lesson_blocks_table),
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
                sa.insert(html_blocks_table),
                html_values,
            )
        if katex_values:
            await self._session.execute(
                sa.insert(katex_blocks_table),
                katex_values,
            )
        if rutube_values:
            await self._session.execute(
                sa.insert(rutube_video_blocks_table),
                rutube_values,
            )
        if code_values:
            await self._session.execute(
                sa.insert(code_blocks_table),
                code_values,
            )
