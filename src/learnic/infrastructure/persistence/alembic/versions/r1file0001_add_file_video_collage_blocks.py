"""add file / video-file / photo-collage lesson blocks

Adds three new values to the ``lesson_block_type`` enum and the
six backing child tables — three on the draft side
(``file_blocks``, ``video_file_blocks``, ``photo_collage_blocks``)
and three mirror tables on the release snapshot side. Same shape
as the ``add_answer_blocks`` migration: each block type gets a
draft child table plus a release child table; the
``course_release_blocks`` parent is shared.

Storage shape:

* ``file_blocks`` / ``video_file_blocks`` carry a single
  ``file_id`` FK to ``files.oid`` plus an optional ``title``.
  ``ON DELETE SET NULL`` mirrors ``products.cover_file_id``:
  if the backing file is purged later the block survives with a
  null reference, and the read-side renders it as a missing-file
  placeholder. Two separate tables — not one ``video_blocks`` —
  to keep the discriminator-to-table mapping 1:1 and avoid a
  fake abstraction over diverging playback contracts (Rutube
  embed vs hosted file player).
* ``photo_collage_blocks`` denormalises items into a JSONB array
  of ``{"file_id": "<uuid>|null", "caption": "<str>|null"}`` —
  same rationale as ``code_blocks.tabs`` / choice ``options``.
  Per-item count invariants are enforced upstream by the
  ``PhotoCollageBlock`` entity; the DB stores trusted shapes.
  Per-item file FKs cannot be expressed inside a JSONB array,
  so referential integrity for collage items is intentionally
  managed at the application boundary (the command handler
  loads each ``file_id`` and validates ownership +
  content-type before persistence).

Revision ID: r1file0001
Revises: z1pivot0001
Create Date: 2026-05-19 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "r1file0001"
down_revision: Union[str, Sequence[str], None] = "z1pivot0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Title column is shared across all three new block types. Kept in sync
# with ``BLOCK_TITLE_MAX_LEN`` in
# ``learnic/entities/course_block/constants.py`` — the entity constant
# is the source of truth; this literal is the migration's snapshot of it.
_BLOCK_TITLE_MAX_LEN = 200


def upgrade() -> None:
    """Upgrade schema.

    Extend ``lesson_block_type`` with three new values and create the
    six backing child tables (3 draft + 3 release). PG 12+ supports
    ``ALTER TYPE ... ADD VALUE`` inside a transaction.
    """
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'file'",
    )
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'video_file'",
    )
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'photo_collage'",
    )

    # ------------------------ draft tables ------------------------ #

    op.create_table(
        "file_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "video_file_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "photo_collage_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    # ----------------------- release tables ----------------------- #

    op.create_table(
        "course_release_file_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "course_release_video_file_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "course_release_photo_collage_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column(
            "title",
            sa.String(_BLOCK_TITLE_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; recreate the
    enum without the three new values after deleting any rows that
    use them on both the draft and snapshot sides.
    """
    for value in ("file", "video_file", "photo_collage"):
        op.execute(
            f"DELETE FROM course_release_blocks WHERE type = '{value}'",
        )
        op.execute(f"DELETE FROM lesson_blocks WHERE type = '{value}'")

    op.drop_table("course_release_photo_collage_blocks")
    op.drop_table("course_release_video_file_blocks")
    op.drop_table("course_release_file_blocks")
    op.drop_table("photo_collage_blocks")
    op.drop_table("video_file_blocks")
    op.drop_table("file_blocks")

    op.execute("ALTER TYPE lesson_block_type RENAME TO lesson_block_type_old")
    op.execute(
        "CREATE TYPE lesson_block_type AS ENUM "
        "('html', 'katex', 'rutube_video', 'code', "
        "'single_choice', 'multi_choice', 'text_input')",
    )
    op.execute(
        "ALTER TABLE lesson_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute(
        "ALTER TABLE course_release_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute("DROP TYPE lesson_block_type_old")
