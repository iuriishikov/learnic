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

Block subtype routing goes through the shared :data:`BLOCK_SPECS`
registry — the same source of truth the forward snapshotter uses —
so every :class:`BlockType` is handled and adding a new variant is
a single registry edit, not another branch here.
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
from learnic.infrastructure.persistence.blocks.registry import (
    BLOCK_SPECS,
    spec_for_row,
)
from learnic.infrastructure.persistence.models.note_block import (
    lesson_blocks_table,
    photo_collage_items_table,
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
    note_release_file_blocks_table,
    note_release_function_graph_blocks_table,
    note_release_html_blocks_table,
    note_release_katex_blocks_table,
    note_release_lessons_table,
    note_release_modules_table,
    note_release_multi_choice_blocks_table,
    note_release_photo_collage_blocks_table,
    note_release_photo_collage_items_table,
    note_release_rutube_video_blocks_table,
    note_release_single_choice_blocks_table,
    note_release_text_input_blocks_table,
    note_release_video_file_blocks_table,
)


class NoteDraftResetterAlchemy(NoteDraftResetter):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def reset(self, release: NoteRelease) -> None:
        # 1. Wipe current draft. CASCADE on FK chains takes care of
        #    note_lessons → lesson_blocks → all child rows.
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
        rows = (await self._session.execute(self._select_blocks(release))).all()
        if not rows:
            return

        block_map: dict[uuid.UUID, uuid.UUID] = {row.oid: uuid.uuid4() for row in rows}

        await self._session.execute(
            sa.insert(lesson_blocks_table),
            [
                {
                    "oid": block_map[row.oid],
                    "lesson_id": lesson_map[row.release_lesson_id],
                    "product_id": release.product_id,
                    "type": (
                        row.type.value if hasattr(row.type, "value") else row.type
                    ),
                    "position": row.position,
                }
                for row in rows
            ],
        )

        # Route every block's subtype payload through the registry so a
        # new BlockType is a single BLOCK_SPECS entry, never another
        # branch here. The 10 column-backed subtypes share their column
        # shape between the draft and release tables, so the registry's
        # ``release_insert_value`` builder produces a draft-ready payload
        # unchanged. Photo-collage is the sole exception: its items live
        # in the ``photo_collage_items`` child table on the draft side
        # (a denormalised JSONB column on the release side), so it is
        # unpacked into child rows explicitly.
        subtype_values: dict[sa.Table, list[dict[str, Any]]] = {
            spec.draft_subtype_table: [] for spec in BLOCK_SPECS.values()
        }
        # Release collage items now live in their own child table
        # (mirroring the draft side); load them keyed by release block
        # oid and unpack into fresh draft photo_collage_items rows.
        collage_items_by_block = await self._load_release_collage_items(
            [
                row.oid
                for row in rows
                if spec_for_row(row).kind is BlockType.PHOTO_COLLAGE
            ],
        )
        collage_item_values: list[dict[str, Any]] = []
        for row in rows:
            new_oid = block_map[row.oid]
            spec = spec_for_row(row)
            if spec.kind is BlockType.PHOTO_COLLAGE:
                subtype_values[spec.draft_subtype_table].append(
                    {"oid": new_oid, "title": row.photo_collage_title},
                )
                collage_item_values.extend(
                    self._collage_item_values(
                        new_oid,
                        collage_items_by_block.get(row.oid, []),
                    ),
                )
            else:
                subtype_values[spec.draft_subtype_table].append(
                    spec.release_insert_value(row, new_oid),
                )

        for table, values in subtype_values.items():
            if values:
                await self._session.execute(sa.insert(table), values)
        if collage_item_values:
            await self._session.execute(
                sa.insert(photo_collage_items_table),
                collage_item_values,
            )

    @staticmethod
    def _collage_item_values(
        block_oid: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        # Release items now come from the
        # ``note_release_photo_collage_items`` child table, already
        # ordered by position; restore needs only ``file_id`` +
        # ``caption``. Item ids are regenerated so the restored draft
        # stays disjoint from the snapshot, mirroring the fresh
        # module / lesson / block ids.
        values: list[dict[str, Any]] = []
        for position, item in enumerate(items):
            raw_file_id = item.get("file_id")
            values.append(
                {
                    "oid": uuid.uuid4(),
                    "block_id": block_oid,
                    "position": position,
                    "file_id": (
                        uuid.UUID(raw_file_id) if raw_file_id is not None else None
                    ),
                    "caption": item.get("caption"),
                },
            )
        return values

    async def _load_release_collage_items(
        self,
        block_oids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[dict[str, Any]]]:
        """Release collage items keyed by release block oid, ordered.

        Items moved from a JSONB column to the
        ``note_release_photo_collage_items`` child table; restore needs
        only ``file_id`` + ``caption`` (item ids are regenerated for the
        new draft).
        """
        if not block_oids:
            return {}
        t = note_release_photo_collage_items_table
        rows = (
            await self._session.execute(
                sa.select(t.c.block_id, t.c.file_id, t.c.caption)
                .where(t.c.block_id.in_(block_oids))
                .order_by(t.c.block_id.asc(), t.c.position.asc()),
            )
        ).all()
        out: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for row in rows:
            out.setdefault(row.block_id, []).append(
                {
                    "file_id": (str(row.file_id) if row.file_id is not None else None),
                    "caption": row.caption,
                },
            )
        return out

    @staticmethod
    def _select_blocks(release: NoteRelease) -> sa.Select[Any]:
        # Reverse of NoteReleaseSnapshotterAlchemy's forward block SELECT:
        # read every release subtype table under the labels the registry's
        # row dispatchers expect, so spec_for_row / release_insert_value
        # work unchanged on these rows. Local aliases keep the join under
        # the 79-col limit given the long ``note_release_*`` table names.
        b = note_release_blocks_table
        html_t = note_release_html_blocks_table
        katex_t = note_release_katex_blocks_table
        rutube_t = note_release_rutube_video_blocks_table
        code_t = note_release_code_blocks_table
        fgraph_t = note_release_function_graph_blocks_table
        single_t = note_release_single_choice_blocks_table
        multi_t = note_release_multi_choice_blocks_table
        text_t = note_release_text_input_blocks_table
        file_t = note_release_file_blocks_table
        video_t = note_release_video_file_blocks_table
        collage_t = note_release_photo_collage_blocks_table
        return (
            sa.select(
                b.c.oid,
                b.c.release_lesson_id,
                b.c.type,
                b.c.position,
                html_t.c.html,
                katex_t.c.source,
                rutube_t.c.external_id.label("rutube_external_id"),
                rutube_t.c.title.label("rutube_title"),
                code_t.c.tabs.label("code_tabs"),
                single_t.c.options.label("single_choice_options"),
                single_t.c.correct_option_id.label(
                    "single_choice_correct_option_id",
                ),
                multi_t.c.options.label("multi_choice_options"),
                multi_t.c.correct_option_ids.label(
                    "multi_choice_correct_option_ids",
                ),
                text_t.c.accepted_answers.label(
                    "text_input_accepted_answers",
                ),
                text_t.c.case_sensitive.label("text_input_case_sensitive"),
                text_t.c.trim_whitespace.label("text_input_trim_whitespace"),
                file_t.c.file_id.label("file_block_file_id"),
                file_t.c.title.label("file_block_title"),
                video_t.c.file_id.label("video_file_block_file_id"),
                video_t.c.title.label("video_file_block_title"),
                collage_t.c.title.label("photo_collage_title"),
                fgraph_t.c.config.label("function_graph_config"),
            )
            .select_from(
                b.outerjoin(html_t, b.c.oid == html_t.c.oid)
                .outerjoin(katex_t, b.c.oid == katex_t.c.oid)
                .outerjoin(rutube_t, b.c.oid == rutube_t.c.oid)
                .outerjoin(code_t, b.c.oid == code_t.c.oid)
                .outerjoin(single_t, b.c.oid == single_t.c.oid)
                .outerjoin(multi_t, b.c.oid == multi_t.c.oid)
                .outerjoin(text_t, b.c.oid == text_t.c.oid)
                .outerjoin(file_t, b.c.oid == file_t.c.oid)
                .outerjoin(video_t, b.c.oid == video_t.c.oid)
                .outerjoin(collage_t, b.c.oid == collage_t.c.oid)
                .outerjoin(fgraph_t, b.c.oid == fgraph_t.c.oid),
            )
            .where(b.c.release_id == release.oid)
        )
