"""photo_collage_items

Move photo-collage items out of the
``photo_collage_blocks.items`` JSONB column into a dedicated
``photo_collage_items`` child table on the draft side. Each item
gets a stable ``oid`` so granular operations (add / remove /
reorder / caption edit) can address one photo by id instead of by
position. Per-item file FKs become real ``files`` references with
``ON DELETE SET NULL`` — the gallery survives backing-file
deletion the same way ``file_blocks`` / ``video_file_blocks`` do.

Release snapshots continue to store items inside a JSONB column
on ``course_release_photo_collage_blocks``. Existing snapshot rows
are backfilled with synthetic ``oid``s so the new reader (which
expects every payload dict to carry one) keeps working against
historical releases.

Revision ID: z2collage0001
Revises: z1pivot0001
Create Date: 2026-05-20 12:00:00.000000

"""

import uuid
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "z2collage0001"
down_revision: Union[str, Sequence[str], None] = "s5cascade0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of ``PHOTO_COLLAGE_CAPTION_MAX_LEN`` from
# ``learnic/entities/course_block/constants.py`` — kept verbatim
# here because migrations cannot import the domain code (entities
# may evolve incompatibly with historical migrations).
_CAPTION_MAX_LEN = 280


def upgrade() -> None:
    """Upgrade schema.

    1. Create ``photo_collage_items`` with FK to
       ``photo_collage_blocks.oid`` (CASCADE) and to ``files.oid``
       (SET NULL).
    2. Backfill rows from the existing ``photo_collage_blocks.items``
       JSONB on the draft side — one row per array element, fresh
       ``oid`` per item, ``position`` from the array index.
    3. Backfill ``oid`` into every item in the release-side JSONB
       so the new reader's payload contract is met for historical
       snapshots.
    4. Drop ``photo_collage_blocks.items``.
    """
    op.create_table(
        "photo_collage_items",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "caption",
            sa.String(_CAPTION_MAX_LEN),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["photo_collage_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "block_id",
            "position",
            name="uq_photo_collage_items_block_position",
        ),
    )
    op.create_index(
        "ix_photo_collage_items_block_id",
        "photo_collage_items",
        ["block_id"],
    )

    bind = op.get_bind()

    # ---- draft backfill: JSONB → photo_collage_items rows ---- #
    block_rows = bind.execute(
        sa.text("SELECT oid, items FROM photo_collage_blocks"),
    ).fetchall()
    inserts: list[dict[str, Any]] = []
    for block in block_rows:
        block_oid = block.oid
        items = block.items or []
        for idx, item in enumerate(items):
            raw_file_id = item.get("file_id")
            caption = item.get("caption")
            inserts.append(
                {
                    "oid": uuid.uuid4(),
                    "block_id": block_oid,
                    "position": idx,
                    "file_id": (
                        uuid.UUID(raw_file_id)
                        if isinstance(raw_file_id, str)
                        else raw_file_id
                    ),
                    "caption": caption,
                },
            )
    if inserts:
        bind.execute(
            sa.text(
                "INSERT INTO photo_collage_items "
                "(oid, block_id, position, file_id, caption) "
                "VALUES (:oid, :block_id, :position, :file_id, :caption)",
            ),
            inserts,
        )

    # ---- release backfill: stamp oid into every JSONB item ---- #
    release_rows = bind.execute(
        sa.text(
            "SELECT oid, items FROM course_release_photo_collage_blocks",
        ),
    ).fetchall()
    for release_row in release_rows:
        items = release_row.items or []
        updated = []
        for item in items:
            new_item = dict(item)
            if "oid" not in new_item or new_item["oid"] is None:
                new_item["oid"] = str(uuid.uuid4())
            updated.append(new_item)
        bind.execute(
            sa.text(
                "UPDATE course_release_photo_collage_blocks "
                "SET items = :items WHERE oid = :oid",
            ).bindparams(
                sa.bindparam("items", type_=JSONB),
            ),
            {"items": updated, "oid": release_row.oid},
        )

    # ---- drop the JSONB column ---- #
    op.drop_column("photo_collage_blocks", "items")


def downgrade() -> None:
    """Downgrade schema.

    1. Recreate the ``photo_collage_blocks.items`` JSONB column.
    2. Rebuild the array from ``photo_collage_items`` ordered by
       ``position``; surviving ``oid`` is preserved inside each
       JSONB entry so a subsequent re-upgrade would not generate
       fresh ids.
    3. Drop ``photo_collage_items``.

    Release-side ``items`` JSONB is left as-is — the ``oid``
    backfill on the upgrade side is forward-compatible (older
    readers ignored unknown keys).
    """
    op.add_column(
        "photo_collage_blocks",
        sa.Column("items", JSONB, nullable=True),
    )

    bind = op.get_bind()
    block_ids = bind.execute(
        sa.text("SELECT oid FROM photo_collage_blocks"),
    ).fetchall()
    for block in block_ids:
        items = bind.execute(
            sa.text(
                "SELECT oid, file_id, caption FROM photo_collage_items "
                "WHERE block_id = :block_id ORDER BY position ASC",
            ),
            {"block_id": block.oid},
        ).fetchall()
        payload = [
            {
                "oid": str(item.oid),
                "file_id": (
                    str(item.file_id) if item.file_id is not None else None
                ),
                "caption": item.caption,
            }
            for item in items
        ]
        bind.execute(
            sa.text(
                "UPDATE photo_collage_blocks "
                "SET items = :items WHERE oid = :oid",
            ).bindparams(sa.bindparam("items", type_=JSONB)),
            {"items": payload, "oid": block.oid},
        )

    op.alter_column(
        "photo_collage_blocks",
        "items",
        nullable=False,
    )

    op.drop_index(
        "ix_photo_collage_items_block_id",
        table_name="photo_collage_items",
    )
    op.drop_table("photo_collage_items")
