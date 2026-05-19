"""Batch-resolve file references inside a lesson-block query result.

Both :class:`CourseContentReaderAlchemy` (draft side) and
:class:`CourseReleaseReaderAlchemy` (release side) SELECT block rows
that may carry file ids in two shapes:

* ``file_block_file_id`` / ``video_file_block_file_id`` — direct FK
  columns selected via subtype-table JOINs.
* ``photo_collage_items`` — a JSONB array of ``{"file_id": "<uuid>",
  "caption": "..."}`` items.

The reader walks every row once with :func:`collect_file_ids`,
issues a single ``IN`` query against ``files`` with
:func:`resolve_file_views`, and passes the resulting
``Mapping[FileID, FileView]`` to the block registry's row dispatcher
— so the per-row ``row_to_view`` functions stay synchronous and
ignorant of storage even though each :class:`FileView` they emit
already carries a short-lived presigned URL.
"""

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from learnic.application.common.persistence.file import FileMeta, FileView
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.file.ids import FileID
from learnic.infrastructure.persistence.models.file import files_table


def collect_file_ids(rows: list[sa.Row[Any]]) -> set[FileID]:
    """Return every file id referenced by a list of block rows.

    Drains the three file-bearing shapes (``file``, ``video_file``,
    ``photo_collage``) without dispatching by ``row.type`` — rows for
    non-file block types have ``NULL`` in the FK columns and ``None``
    in ``photo_collage_items`` thanks to the OUTER JOIN, so the
    accumulator naturally skips them.
    """
    ids: set[FileID] = set()
    for row in rows:
        fid = row.file_block_file_id
        if fid is not None:
            ids.add(FileID(fid))
        vfid = row.video_file_block_file_id
        if vfid is not None:
            ids.add(FileID(vfid))
        items = row.photo_collage_items
        if items is None:
            continue
        for item in items:
            raw = item.get("file_id")
            if raw is None:
                continue
            ids.add(FileID(uuid.UUID(raw)))
    return ids


async def resolve_file_views(
    session: AsyncSession,
    file_storage: FileStorage,
    ids: set[FileID],
) -> dict[FileID, FileView]:
    """Batch-fetch file metadata + sign presigned URLs.

    One SQL ``IN`` query against ``files`` (filtered for non-
    soft-deleted rows) plus N HMAC signings. Ids that no longer
    resolve to a live row are silently absent from the result —
    a block whose backing file was purged degrades to a
    "missing file" placeholder rather than an exception.
    """
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
    rows = (await session.execute(stmt)).all()
    result: dict[FileID, FileView] = {}
    for row in rows:
        meta = FileMeta(
            oid=FileID(row.oid),
            storage_name=row.storage_name,
            bucket=row.bucket,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
        )
        result[meta.oid] = await FileView.of(meta, file_storage)
    return result
