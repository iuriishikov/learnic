"""release photo_collage_items

Move release photo-collage items out of the denormalised
``note_release_photo_collage_blocks.items`` JSONB column into a
dedicated ``note_release_photo_collage_items`` child table, mirroring
the draft side (``photo_collage_items``, see ``z2collage0001``). Reads,
the release-pin probe (``is_referenced_by_release``) and storage-usage
accounting become plain joins instead of JSONB unnesting.

``oid`` is a fresh per-release surrogate PK — release tables never
reuse draft ids — and ``source_item_id`` carries the draft item id so
the reader exposes the same item identity the JSONB did (variant A).
``file_id`` keeps ``ON DELETE SET NULL`` like the other file-backed
release mirrors. Existing JSONB rows are backfilled one row per array
element, ``position`` from the array index, ``source_item_id`` from the
item's stored ``oid``.

Revision ID: relcollage0001
Revises: distconsent0001
Create Date: 2026-06-16 00:00:00.000000

"""

import uuid
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "relcollage0001"
down_revision: Union[str, Sequence[str], None] = "distconsent0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of ``PHOTO_COLLAGE_CAPTION_MAX_LEN`` from
# ``learnic/entities/note_block/constants.py`` — kept verbatim here
# because migrations cannot import the domain code (entities may
# evolve incompatibly with historical migrations).
_CAPTION_MAX_LEN = 280


def upgrade() -> None:
    """Upgrade schema.

    1. Create ``note_release_photo_collage_items`` with FK to
       ``note_release_photo_collage_blocks.oid`` (CASCADE) and to
       ``files.oid`` (SET NULL).
    2. Backfill rows from the existing release-side
       ``note_release_photo_collage_blocks.items`` JSONB — one row per
       array element, fresh ``oid`` per row, ``source_item_id`` from
       the item's stored ``oid``, ``position`` from the array index.
    3. Drop ``note_release_photo_collage_blocks.items``.
    """
    op.create_table(
        "note_release_photo_collage_items",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.Uuid(), nullable=False),
        sa.Column("source_item_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "caption",
            sa.String(_CAPTION_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["note_release_photo_collage_blocks.oid"],
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
            name="uq_note_release_photo_collage_items_block_position",
        ),
    )
    op.create_index(
        "ix_note_release_photo_collage_items_block_id",
        "note_release_photo_collage_items",
        ["block_id"],
    )

    bind = op.get_bind()

    # ---- backfill: release JSONB → child rows ---- #
    block_rows = bind.execute(
        sa.text(
            "SELECT oid, items FROM note_release_photo_collage_blocks",
        ),
    ).fetchall()
    inserts: list[dict[str, Any]] = []
    for block in block_rows:
        items = block.items or []
        for idx, item in enumerate(items):
            raw_source = item.get("oid")
            raw_file_id = item.get("file_id")
            inserts.append(
                {
                    "oid": uuid.uuid4(),
                    "block_id": block.oid,
                    "source_item_id": (
                        uuid.UUID(raw_source)
                        if isinstance(raw_source, str)
                        else raw_source
                    ),
                    "position": idx,
                    "file_id": (
                        uuid.UUID(raw_file_id)
                        if isinstance(raw_file_id, str)
                        else raw_file_id
                    ),
                    "caption": item.get("caption"),
                },
            )
    if inserts:
        bind.execute(
            sa.text(
                "INSERT INTO note_release_photo_collage_items "
                "(oid, block_id, source_item_id, position, file_id, "
                "caption) VALUES (:oid, :block_id, :source_item_id, "
                ":position, :file_id, :caption)",
            ),
            inserts,
        )

    op.drop_column("note_release_photo_collage_blocks", "items")


def downgrade() -> None:
    """Downgrade schema.

    1. Recreate the ``note_release_photo_collage_blocks.items`` JSONB
       column.
    2. Rebuild the array from ``note_release_photo_collage_items``
       ordered by ``position``; ``source_item_id`` is written back into
       each entry's ``oid`` so a subsequent re-upgrade restores the
       same identities.
    3. Drop ``note_release_photo_collage_items``.
    """
    op.add_column(
        "note_release_photo_collage_blocks",
        sa.Column("items", JSONB, nullable=True),
    )

    bind = op.get_bind()
    block_ids = bind.execute(
        sa.text("SELECT oid FROM note_release_photo_collage_blocks"),
    ).fetchall()
    for block in block_ids:
        items = bind.execute(
            sa.text(
                "SELECT source_item_id, file_id, caption "
                "FROM note_release_photo_collage_items "
                "WHERE block_id = :block_id ORDER BY position ASC",
            ),
            {"block_id": block.oid},
        ).fetchall()
        payload = [
            {
                "oid": (
                    str(item.source_item_id)
                    if item.source_item_id is not None
                    else str(uuid.uuid4())
                ),
                "file_id": (str(item.file_id) if item.file_id is not None else None),
                "caption": item.caption,
            }
            for item in items
        ]
        bind.execute(
            sa.text(
                "UPDATE note_release_photo_collage_blocks "
                "SET items = :items WHERE oid = :oid",
            ).bindparams(sa.bindparam("items", type_=JSONB)),
            {"items": payload, "oid": block.oid},
        )

    op.alter_column(
        "note_release_photo_collage_blocks",
        "items",
        nullable=False,
    )

    op.drop_index(
        "ix_note_release_photo_collage_items_block_id",
        table_name="note_release_photo_collage_items",
    )
    op.drop_table("note_release_photo_collage_items")
