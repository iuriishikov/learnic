"""Adapters for note releases — Gateway, Snapshotter, Reader.

The Gateway and entity-mapping path is conventional imperative
SA. The Snapshotter is Core-only — it copies draft rows into the
snapshot mirror tables in three batched INSERT phases (modules →
lessons → blocks + per-type child tables), generating fresh
UUIDs in Python so the new rows can FK to the new release row
without depending on draft ids that may later be deleted.

The Reader walks the snapshot tables in the same Core style as
:class:`NoteContentReaderAlchemy` for the draft side.
"""

import uuid
from abc import abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar, Final, Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_content import (
    LessonBlockView,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseBlockGateway,
    NoteReleaseContentView,
    NoteReleaseGateway,
    NoteReleaseReader,
    NoteReleaseSnapshotter,
    NoteReleaseSummaryView,
    ReleaseLessonView,
    ReleaseModuleView,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_block.models import LessonBlock
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.blocks.file_resolver import (
    collect_file_ids,
    resolve_file_views,
)
from learnic.infrastructure.persistence.blocks.registry import (
    BLOCK_SPECS,
    _CommonBlockAttrs,
    spec_for_row,
)
from learnic.infrastructure.persistence.models.note_block import (
    code_blocks_table,
    file_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    multi_choice_blocks_table,
    photo_collage_blocks_table,
    photo_collage_items_table,
    rutube_video_blocks_table,
    single_choice_blocks_table,
    text_input_blocks_table,
    video_file_blocks_table,
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
    note_release_html_blocks_table,
    note_release_katex_blocks_table,
    note_release_lessons_table,
    note_release_modules_table,
    note_release_multi_choice_blocks_table,
    note_release_photo_collage_blocks_table,
    note_release_rutube_video_blocks_table,
    note_release_single_choice_blocks_table,
    note_release_text_input_blocks_table,
    note_release_video_file_blocks_table,
    note_releases_table,
)


# ============================== gateway ============================== #


class NoteReleaseMapperAlchemy(NoteReleaseGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: NoteReleaseID,
    ) -> NoteRelease | None:
        stmt = sa.select(NoteRelease).where(
            note_releases_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def latest_for_product(
        self,
        product_id: ProductID,
    ) -> NoteRelease | None:
        stmt = (
            sa.select(NoteRelease)
            .where(note_releases_table.c.product_id == product_id)
            .order_by(note_releases_table.c.ordinal.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def count_for_product(self, product_id: ProductID) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(note_releases_table)
            .where(note_releases_table.c.product_id == product_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())


# ============================== snapshotter ============================== #


_IdMap = dict[uuid.UUID, uuid.UUID]


class _SnapshotPhase(Protocol):
    """One step of the draft → release copy pipeline.

    Phases run sequentially; each returns an old-id → new-id mapping
    keyed by ``key`` into the shared ``prior_maps`` dict so later
    phases can rewrite FK references to ids that were just generated.
    Phases that produce no descendants (the last leaf, currently
    blocks) may return an empty dict.
    """

    key: str

    async def run(
        self,
        session: AsyncSession,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> _IdMap: ...


class _RowMappingPhase(_SnapshotPhase):
    """Shared shape for "SELECT draft rows → INSERT release rows" phases.

    Subclasses pin the target table, the SELECT to drive the copy,
    and the per-row INSERT payload builder. The skeleton — generate a
    fresh uuid per source row, executemany the inserts, return the
    mapping — lives here so adding another straightforward
    sub-resource (e.g. lesson attachments) is one class plus one line
    in ``_PHASES``.
    """

    table: ClassVar[sa.Table]

    @abstractmethod
    def _select(self, release: NoteRelease) -> sa.Select[Any]: ...

    @abstractmethod
    def _build_value(
        self,
        row: sa.Row[Any],
        new_oid: uuid.UUID,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> dict[str, Any]: ...

    async def run(
        self,
        session: AsyncSession,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> _IdMap:
        rows = (await session.execute(self._select(release))).all()
        if not rows:
            return {}
        mapping: _IdMap = {row.oid: uuid.uuid4() for row in rows}
        values = [
            self._build_value(row, mapping[row.oid], release, prior_maps)
            for row in rows
        ]
        await session.execute(sa.insert(self.table), values)
        return mapping


class _ModulesSnapshotPhase(_RowMappingPhase):
    key = "modules"
    table = note_release_modules_table

    @override
    def _select(self, release: NoteRelease) -> sa.Select[Any]:
        return sa.select(
            note_modules_table.c.oid,
            note_modules_table.c.title,
            note_modules_table.c.description,
            note_modules_table.c.position,
        ).where(note_modules_table.c.product_id == release.product_id)

    @override
    def _build_value(
        self,
        row: sa.Row[Any],
        new_oid: uuid.UUID,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> dict[str, Any]:
        return {
            "oid": new_oid,
            "release_id": release.oid,
            "source_module_id": row.oid,
            "title": row.title,
            "description": row.description,
            "position": row.position,
        }


class _LessonsSnapshotPhase(_RowMappingPhase):
    key = "lessons"
    table = note_release_lessons_table

    @override
    def _select(self, release: NoteRelease) -> sa.Select[Any]:
        return sa.select(
            note_lessons_table.c.oid,
            note_lessons_table.c.module_id,
            note_lessons_table.c.title,
            note_lessons_table.c.position,
        ).where(note_lessons_table.c.product_id == release.product_id)

    @override
    def _build_value(
        self,
        row: sa.Row[Any],
        new_oid: uuid.UUID,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> dict[str, Any]:
        return {
            "oid": new_oid,
            "release_id": release.oid,
            "release_module_id": prior_maps["modules"][row.module_id],
            "source_lesson_id": row.oid,
            "title": row.title,
            "position": row.position,
        }


async def _load_release_collage_items_payload(
    session: AsyncSession,
    rows: Sequence[sa.Row[Any]],
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Batch-load draft items for the collage rows in the snapshot SELECT.

    Returns ``{block_id: [item dict, ...]}`` keyed by the draft block
    id; ``[item dict, ...]`` is the canonical ``{"oid", "file_id",
    "caption"}`` payload list ready to be persisted into the release
    side's JSONB column. ``oid`` is copied verbatim from the draft
    item — release-time snapshot identity equals draft identity so
    URL bookmarks tied to a specific photo survive the snapshot.
    """
    from learnic.entities.note_block.enums import (  # local import to avoid cycle  # noqa: E501, PLC0415
        BlockType,
    )

    collage_ids = [
        row.oid
        for row in rows
        if (
            row.type
            if isinstance(row.type, BlockType)
            else BlockType(row.type)
        )
        is BlockType.PHOTO_COLLAGE
    ]
    if not collage_ids:
        return {}
    stmt = (
        sa.select(
            photo_collage_items_table.c.oid,
            photo_collage_items_table.c.block_id,
            photo_collage_items_table.c.file_id,
            photo_collage_items_table.c.caption,
        )
        .where(photo_collage_items_table.c.block_id.in_(collage_ids))
        .order_by(
            photo_collage_items_table.c.block_id.asc(),
            photo_collage_items_table.c.position.asc(),
        )
    )
    items_rows = (await session.execute(stmt)).all()
    out: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for row in items_rows:
        out.setdefault(row.block_id, []).append(
            {
                "oid": str(row.oid),
                "file_id": (
                    str(row.file_id) if row.file_id is not None else None
                ),
                "caption": row.caption,
            },
        )
    return out


class _RowWithCollageItems:
    """Read-only proxy exposing ``photo_collage_items`` on a snapshot row.

    Same shim used by the gateway / draft reader — see those modules
    for the broader rationale.
    """

    __slots__ = ("_row", "_items")

    def __init__(
        self,
        row: sa.Row[Any],
        items: list[dict[str, Any]],
    ) -> None:
        self._row = row
        self._items = items

    @property
    def photo_collage_items(self) -> list[dict[str, Any]]:
        return self._items

    def __getattr__(self, name: str) -> Any:
        return getattr(self._row, name)


def _attach_release_collage_items(
    rows: Sequence[sa.Row[Any]],
    items_by_block: dict[uuid.UUID, list[dict[str, Any]]],
) -> list[Any]:
    from learnic.entities.note_block.enums import (  # local import to avoid cycle  # noqa: E501, PLC0415
        BlockType,
    )

    out: list[Any] = []
    for row in rows:
        block_type = (
            row.type
            if isinstance(row.type, BlockType)
            else BlockType(row.type)
        )
        if block_type is not BlockType.PHOTO_COLLAGE:
            out.append(row)
            continue
        items = items_by_block.get(row.oid, [])
        out.append(_RowWithCollageItems(row, items))
    return out


class _BlocksSnapshotPhase(_SnapshotPhase):
    """Block phase is two-stage: parent row + per-type subtype row.

    Doesn't fit ``_RowMappingPhase`` because each source row writes to
    two tables — the polymorphic parent and one of four typed
    children. Subtype routing lives inside :meth:`_partition_subtypes`
    so the per-stage code stays linear.
    """

    key = "blocks"

    @override
    async def run(
        self,
        session: AsyncSession,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> _IdMap:
        rows = list((await session.execute(self._select(release))).all())
        if not rows:
            return {}

        # Photo-collage items live in a child table on the draft side
        # but are persisted as a denormalised JSONB array on the
        # release side. Load each collage's items once and stash them
        # on a per-row proxy so the registry's existing
        # ``_photo_collage_release_insert_value`` reads them under
        # the same attribute name it expects on the release reader
        # path.
        collage_payload = await _load_release_collage_items_payload(
            session,
            rows,
        )
        attached_rows = _attach_release_collage_items(rows, collage_payload)

        mapping: _IdMap = {row.oid: uuid.uuid4() for row in attached_rows}
        await session.execute(
            sa.insert(note_release_blocks_table),
            [
                self._parent_value(row, mapping[row.oid], release, prior_maps)
                for row in attached_rows
            ],
        )

        for table, values in self._partition_subtypes(
            attached_rows, mapping,
        ).items():
            if values:
                await session.execute(sa.insert(table), values)
        return mapping

    @staticmethod
    def _select(release: NoteRelease) -> sa.Select[Any]:
        return (
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
                single_choice_blocks_table.c.options.label(
                    "single_choice_options",
                ),
                single_choice_blocks_table.c.correct_option_id.label(
                    "single_choice_correct_option_id",
                ),
                multi_choice_blocks_table.c.options.label(
                    "multi_choice_options",
                ),
                multi_choice_blocks_table.c.correct_option_ids.label(
                    "multi_choice_correct_option_ids",
                ),
                text_input_blocks_table.c.accepted_answers.label(
                    "text_input_accepted_answers",
                ),
                text_input_blocks_table.c.case_sensitive.label(
                    "text_input_case_sensitive",
                ),
                text_input_blocks_table.c.trim_whitespace.label(
                    "text_input_trim_whitespace",
                ),
                file_blocks_table.c.file_id.label("file_block_file_id"),
                file_blocks_table.c.title.label("file_block_title"),
                video_file_blocks_table.c.file_id.label(
                    "video_file_block_file_id",
                ),
                video_file_blocks_table.c.title.label(
                    "video_file_block_title",
                ),
                photo_collage_blocks_table.c.title.label(
                    "photo_collage_title",
                ),
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
                )
                .outerjoin(
                    single_choice_blocks_table,
                    lesson_blocks_table.c.oid == single_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    multi_choice_blocks_table,
                    lesson_blocks_table.c.oid == multi_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    text_input_blocks_table,
                    lesson_blocks_table.c.oid == text_input_blocks_table.c.oid,
                )
                .outerjoin(
                    file_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                )
                .outerjoin(
                    video_file_blocks_table,
                    lesson_blocks_table.c.oid == video_file_blocks_table.c.oid,
                )
                .outerjoin(
                    photo_collage_blocks_table,
                    lesson_blocks_table.c.oid == photo_collage_blocks_table.c.oid,
                ),
            )
            .where(lesson_blocks_table.c.product_id == release.product_id)
        )

    @staticmethod
    def _parent_value(
        row: sa.Row[Any],
        new_oid: uuid.UUID,
        release: NoteRelease,
        prior_maps: dict[str, _IdMap],
    ) -> dict[str, Any]:
        return {
            "oid": new_oid,
            "release_id": release.oid,
            "release_lesson_id": prior_maps["lessons"][row.lesson_id],
            "source_block_id": row.oid,
            "type": row.type.value if hasattr(row.type, "value") else row.type,
            "position": row.position,
        }

    @staticmethod
    def _partition_subtypes(
        rows: Sequence[sa.Row[Any]],
        mapping: _IdMap,
    ) -> dict[sa.Table, list[dict[str, Any]]]:
        """Route each block row to its subtype INSERT bucket via the registry."""
        buckets: dict[sa.Table, list[dict[str, Any]]] = {
            spec.release_subtype_table: [] for spec in BLOCK_SPECS.values()
        }
        for row in rows:
            spec = spec_for_row(row)
            buckets[spec.release_subtype_table].append(
                spec.release_insert_value(row, mapping[row.oid]),
            )
        return buckets


_PHASES: Final[tuple[_SnapshotPhase, ...]] = (
    _ModulesSnapshotPhase(),
    _LessonsSnapshotPhase(),
    _BlocksSnapshotPhase(),
)


class NoteReleaseSnapshotterAlchemy(NoteReleaseSnapshotter):
    """Copies draft content into release-snapshot tables.

    The draft → release copy is a fixed sequence of phases declared
    in ``_PHASES``: each phase SELECTs from a draft table, generates
    fresh UUIDs in Python so the new rows don't FK back to draft ids
    that may later be deleted, and bulk-INSERTs through
    ``executemany``. Phases hand each other id maps via ``prior_maps``
    so child phases can rewrite FK references.

    Adding a new sub-resource (e.g. lesson attachments) is a new
    ``_RowMappingPhase`` subclass plus one line in ``_PHASES`` —
    the orchestrator below stays untouched.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def snapshot(self, release: NoteRelease) -> None:
        prior_maps: dict[str, _IdMap] = {}
        for phase in _PHASES:
            prior_maps[phase.key] = await phase.run(
                self._session,
                release,
                prior_maps,
            )


# ============================== reader ============================== #


class NoteReleaseReaderAlchemy(NoteReleaseReader):
    def __init__(
        self,
        session: AsyncSession,
        file_storage: FileStorage,
    ) -> None:
        self._session: Final = session
        self._file_storage: Final = file_storage

    @override
    async def list_for_product(
        self,
        product_id: ProductID,
    ) -> list[NoteReleaseSummaryView]:
        stmt = (
            sa.select(
                note_releases_table.c.oid,
                note_releases_table.c.ordinal,
                note_releases_table.c.major,
                note_releases_table.c.minor,
                note_releases_table.c.patch,
                note_releases_table.c.kind,
                note_releases_table.c.notes,
                note_releases_table.c.released_at,
                note_releases_table.c.released_by,
            )
            .where(note_releases_table.c.product_id == product_id)
            .order_by(note_releases_table.c.ordinal.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            NoteReleaseSummaryView(
                oid=NoteReleaseID(row.oid),
                ordinal=row.ordinal,
                major=row.major,
                minor=row.minor,
                patch=row.patch,
                kind=NoteReleaseKind(row.kind),
                notes=row.notes,
                released_at=row.released_at,
                released_by=UserID(row.released_by),
            )
            for row in rows
        ]

    @override
    async def get_content(
        self,
        release_id: NoteReleaseID,
    ) -> NoteReleaseContentView | None:
        meta_row = (
            await self._session.execute(
                sa.select(
                    note_releases_table.c.oid,
                    note_releases_table.c.product_id,
                    note_releases_table.c.ordinal,
                    note_releases_table.c.major,
                    note_releases_table.c.minor,
                    note_releases_table.c.patch,
                    note_releases_table.c.kind,
                    note_releases_table.c.notes,
                    note_releases_table.c.released_at,
                ).where(note_releases_table.c.oid == release_id),
            )
        ).one_or_none()
        if meta_row is None:
            return None

        modules_rows = (
            await self._session.execute(
                sa.select(
                    note_release_modules_table.c.oid,
                    note_release_modules_table.c.title,
                    note_release_modules_table.c.description,
                    note_release_modules_table.c.position,
                )
                .where(note_release_modules_table.c.release_id == release_id)
                .order_by(note_release_modules_table.c.position.asc()),
            )
        ).all()

        lessons_rows = (
            await self._session.execute(
                sa.select(
                    note_release_lessons_table.c.oid,
                    note_release_lessons_table.c.release_module_id,
                    note_release_lessons_table.c.title,
                    note_release_lessons_table.c.position,
                )
                .where(note_release_lessons_table.c.release_id == release_id)
                .order_by(
                    note_release_lessons_table.c.release_module_id.asc(),
                    note_release_lessons_table.c.position.asc(),
                ),
            )
        ).all()

        blocks_rows = (
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
                    note_release_single_choice_blocks_table.c.options.label(
                        "single_choice_options",
                    ),
                    note_release_single_choice_blocks_table.c.correct_option_id.label(  # noqa: E501
                        "single_choice_correct_option_id",
                    ),
                    note_release_multi_choice_blocks_table.c.options.label(
                        "multi_choice_options",
                    ),
                    note_release_multi_choice_blocks_table.c.correct_option_ids.label(  # noqa: E501
                        "multi_choice_correct_option_ids",
                    ),
                    note_release_text_input_blocks_table.c.accepted_answers.label(  # noqa: E501
                        "text_input_accepted_answers",
                    ),
                    note_release_text_input_blocks_table.c.case_sensitive.label(  # noqa: E501
                        "text_input_case_sensitive",
                    ),
                    note_release_text_input_blocks_table.c.trim_whitespace.label(  # noqa: E501
                        "text_input_trim_whitespace",
                    ),
                    note_release_file_blocks_table.c.file_id.label(
                        "file_block_file_id",
                    ),
                    note_release_file_blocks_table.c.title.label(
                        "file_block_title",
                    ),
                    note_release_video_file_blocks_table.c.file_id.label(
                        "video_file_block_file_id",
                    ),
                    note_release_video_file_blocks_table.c.title.label(
                        "video_file_block_title",
                    ),
                    note_release_photo_collage_blocks_table.c["items"].label(
                        "photo_collage_items",
                    ),
                    note_release_photo_collage_blocks_table.c.title.label(
                        "photo_collage_title",
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
                    )
                    .outerjoin(
                        note_release_single_choice_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_single_choice_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_multi_choice_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_multi_choice_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_text_input_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_text_input_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_file_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_file_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_video_file_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_video_file_blocks_table.c.oid,
                    )
                    .outerjoin(
                        note_release_photo_collage_blocks_table,
                        note_release_blocks_table.c.oid
                        == note_release_photo_collage_blocks_table.c.oid,
                    ),
                )
                .where(note_release_blocks_table.c.release_id == release_id)
                .order_by(
                    note_release_blocks_table.c.release_lesson_id.asc(),
                    note_release_blocks_table.c.position.asc(),
                ),
            )
        ).all()

        files_by_id = await resolve_file_views(
            self._session,
            self._file_storage,
            collect_file_ids(list(blocks_rows)),
        )

        blocks_by_lesson: dict[uuid.UUID, list[LessonBlockView]] = {}
        for row in blocks_rows:
            blocks_by_lesson.setdefault(
                row.release_lesson_id,
                [],
            ).append(spec_for_row(row).row_to_view(row, files_by_id))

        lessons_by_module: dict[uuid.UUID, list[ReleaseLessonView]] = {}
        for row in lessons_rows:
            lessons_by_module.setdefault(
                row.release_module_id,
                [],
            ).append(
                ReleaseLessonView(
                    oid=NoteLessonID(row.oid),
                    title=row.title,
                    position=row.position,
                    blocks=blocks_by_lesson.get(row.oid, []),
                ),
            )

        modules: list[ReleaseModuleView] = [
            ReleaseModuleView(
                oid=NoteModuleID(row.oid),
                title=row.title,
                description=row.description,
                position=row.position,
                lessons=lessons_by_module.get(row.oid, []),
            )
            for row in modules_rows
        ]

        return NoteReleaseContentView(
            release_id=NoteReleaseID(meta_row.oid),
            product_id=ProductID(meta_row.product_id),
            ordinal=meta_row.ordinal,
            major=meta_row.major,
            minor=meta_row.minor,
            patch=meta_row.patch,
            kind=NoteReleaseKind(meta_row.kind),
            notes=meta_row.notes,
            released_at=meta_row.released_at,
            modules=modules,
        )


# ============================== release block gateway ============================== #


def _select_release_block_with_id(oid: LessonBlockID) -> sa.Select[Any]:
    """SELECT one release block + its subtype columns + product id.

    Same shape as :meth:`NoteReleaseReaderAlchemy.get_content`'s
    blocks select, but narrowed to a single ``oid`` and joined with
    ``note_releases`` to surface ``product_id`` (consumed by the
    check/reveal handlers for enrollment lookup).
    """
    return (
        sa.select(
            note_release_blocks_table.c.oid,
            note_release_blocks_table.c.release_lesson_id.label("lesson_id"),
            note_releases_table.c.product_id,
            note_release_blocks_table.c.type,
            note_release_blocks_table.c.position,
            note_releases_table.c.released_at.label("created_at"),
            note_releases_table.c.released_at.label("updated_at"),
            note_release_html_blocks_table.c.html,
            note_release_katex_blocks_table.c.source,
            note_release_rutube_video_blocks_table.c.external_id.label(
                "rutube_external_id",
            ),
            note_release_rutube_video_blocks_table.c.title.label(
                "rutube_title",
            ),
            note_release_code_blocks_table.c.tabs.label("code_tabs"),
            note_release_single_choice_blocks_table.c.options.label(
                "single_choice_options",
            ),
            note_release_single_choice_blocks_table.c.correct_option_id.label(
                "single_choice_correct_option_id",
            ),
            note_release_multi_choice_blocks_table.c.options.label(
                "multi_choice_options",
            ),
            note_release_multi_choice_blocks_table.c.correct_option_ids.label(
                "multi_choice_correct_option_ids",
            ),
            note_release_text_input_blocks_table.c.accepted_answers.label(
                "text_input_accepted_answers",
            ),
            note_release_text_input_blocks_table.c.case_sensitive.label(
                "text_input_case_sensitive",
            ),
            note_release_text_input_blocks_table.c.trim_whitespace.label(
                "text_input_trim_whitespace",
            ),
            note_release_file_blocks_table.c.file_id.label(
                "file_block_file_id",
            ),
            note_release_file_blocks_table.c.title.label("file_block_title"),
            note_release_video_file_blocks_table.c.file_id.label(
                "video_file_block_file_id",
            ),
            note_release_video_file_blocks_table.c.title.label(
                "video_file_block_title",
            ),
            note_release_photo_collage_blocks_table.c["items"].label(
                "photo_collage_items",
            ),
            note_release_photo_collage_blocks_table.c.title.label(
                "photo_collage_title",
            ),
        )
        .select_from(
            note_release_blocks_table.join(
                note_releases_table,
                note_release_blocks_table.c.release_id
                == note_releases_table.c.oid,
            )
            .outerjoin(
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
            )
            .outerjoin(
                note_release_single_choice_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_single_choice_blocks_table.c.oid,
            )
            .outerjoin(
                note_release_multi_choice_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_multi_choice_blocks_table.c.oid,
            )
            .outerjoin(
                note_release_text_input_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_text_input_blocks_table.c.oid,
            )
            .outerjoin(
                note_release_file_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_file_blocks_table.c.oid,
            )
            .outerjoin(
                note_release_video_file_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_video_file_blocks_table.c.oid,
            )
            .outerjoin(
                note_release_photo_collage_blocks_table,
                note_release_blocks_table.c.oid
                == note_release_photo_collage_blocks_table.c.oid,
            ),
        )
        .where(note_release_blocks_table.c.oid == oid)
    )


class NoteReleaseBlockGatewayAlchemy(NoteReleaseBlockGateway):
    """Hydrate one release block by id into its domain entity.

    The block carries the release-side ``release_lesson_id`` in
    its ``lesson_id`` field (not the original draft id) and the
    release's ``released_at`` in both timestamp fields — neither
    is consumed by check / reveal flows. The important fields are
    ``oid`` (caller's reference), ``product_id`` (used for the
    enrollment check), and the subtype payload (used by
    ``block.check(...)``).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: LessonBlockID,
    ) -> LessonBlock | None:
        row = (
            await self._session.execute(_select_release_block_with_id(oid))
        ).one_or_none()
        if row is None:
            return None
        common = _CommonBlockAttrs(
            oid=LessonBlockID(row.oid),
            lesson_id=NoteLessonID(row.lesson_id),
            product_id=ProductID(row.product_id),
            position=row.position,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        return spec_for_row(row).row_to_entity(row, common)
