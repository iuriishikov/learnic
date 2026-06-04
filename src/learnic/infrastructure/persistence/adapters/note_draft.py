"""Note draft resetter — restores draft tables from a release snapshot.

Mirror of :class:`NoteReleaseSnapshotterAlchemy` (forward draft →
snapshot) but in the reverse direction: snapshot → draft. Used by
``ResetNoteDraftCommandHandler`` to discard in-progress draft
edits and revert to a previously published release.

Operates in three phases (modules → lessons → blocks + child
tables) within the caller's transaction. Generates fresh UUIDs
for every restored row so draft ids stay disjoint from snapshot
ids. Cascading deletes on the draft side fan out from
``note_modules`` (CASCADE → lessons → blocks → child rows), so
a single ``DELETE FROM note_modules WHERE product_id = ?`` is
all we need to wipe the draft.
"""

import uuid
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_draft import (
    NoteDraftResetter,
)
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_release.models import NoteRelease
from learnic.infrastructure.persistence.models.note_block import (
    code_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    rutube_video_blocks_table,
)
from learnic.infrastructure.persistence.models.note_lesson import (
    note_lessons_table,
)
from learnic.infrastructure.persistence.models.note_module import (
    note_modules_table,
)
from learnic.infrastructure.persistence.models.note_release import (
    note_release_blocks_table,
    note_release_code_blocks_table,
    note_release_html_blocks_table,
    note_release_katex_blocks_table,
    note_release_lessons_table,
    note_release_modules_table,
    note_release_rutube_video_blocks_table,
)


class NoteDraftResetterAlchemy(NoteDraftResetter):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def reset(self, release: NoteRelease) -> None:
        # 1. Wipe current draft. CASCADE on FK chains takes care of
        #    note_lessons → lesson_blocks → html/katex/video child rows.
        await self._session.execute(
            sa.delete(note_modules_table).where(
                note_modules_table.c.product_id == release.product_id,
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
        release: NoteRelease,
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    note_release_modules_table.c.oid,
                    note_release_modules_table.c.title,
                    note_release_modules_table.c.description,
                    note_release_modules_table.c.position,
                ).where(
                    note_release_modules_table.c.release_id == release.oid,
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
            sa.insert(note_modules_table),
            values,
        )
        return mapping

    async def _restore_lessons(
        self,
        release: NoteRelease,
        module_map: dict[uuid.UUID, uuid.UUID],
    ) -> dict[uuid.UUID, uuid.UUID]:
        rows = (
            await self._session.execute(
                sa.select(
                    note_release_lessons_table.c.oid,
                    note_release_lessons_table.c.release_module_id,
                    note_release_lessons_table.c.title,
                    note_release_lessons_table.c.position,
                ).where(
                    note_release_lessons_table.c.release_id == release.oid,
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
            sa.insert(note_lessons_table),
            values,
        )
        return mapping

    async def _restore_blocks(
        self,
        release: NoteRelease,
        lesson_map: dict[uuid.UUID, uuid.UUID],
    ) -> None:
        rows = (
            await self._session.execute(
                sa.select(
                    note_release_blocks_table.c.oid,
                    note_release_blocks_table.c.release_lesson_id,
                    note_release_blocks_table.c.type,
                    note_release_blocks_table.c.position,
                    note_release_html_blocks_table.c.html,
                    note_release_katex_blocks_table.c.source,
                    note_release_rutube_video_blocks_table.c.external_id.label(
                        "rutube_external_id",
                    ),
                    note_release_rutube_video_blocks_table.c.title.label(
                        "rutube_title",
                    ),
                    note_release_code_blocks_table.c.tabs.label(
                        "code_tabs",
                    ),
                )
                .select_from(
                    note_release_blocks_table.outerjoin(
                        note_release_html_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_html_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_katex_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_katex_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_rutube_video_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_rutube_video_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_code_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_code_blocks_table.c.oid,
                    ),
                )
                .where(note_release_blocks_table.c.release_id == release.oid),
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
