"""add interactive answer lesson blocks (single/multi choice + text input)

Adds three new values to the ``lesson_block_type`` enum and the
six backing child tables — three on the draft side
(``single_choice_blocks``, ``multi_choice_blocks``,
``text_input_blocks``) and three mirror tables on the release
snapshot side. The question prompt itself is NOT carried by
these blocks — it lives in a preceding HTML block; these tables
hold only the answer field configuration and the (server-side,
never leaked through the public release view) correctness data.

Storage shape:

* Choice options are denormalized into a JSONB array of
  ``{"oid": "<uuid>", "label": "<str>"}`` — same rationale as
  ``code_blocks.tabs``. The application never queries inside
  the array; uniqueness / count invariants are enforced upstream
  by the domain entity.
* Single-choice keeps ``correct_option_id`` as a typed UUID
  column. Multi-choice uses a JSONB UUID-string array
  (``correct_option_ids``) — kept homogeneous with options
  rather than fighting asyncpg's ``UUID[]`` adapter for a
  payload that is never queried by element.
* Text-input answers go into a JSONB string array, with
  ``case_sensitive`` / ``trim_whitespace`` flags as boolean
  columns. Normalisation happens at check-time on the entity.

Revision ID: p0k1l2m3n4o5
Revises: be01f2a3b4c5
Create Date: 2026-05-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "p0k1l2m3n4o5"
down_revision: Union[str, Sequence[str], None] = "be01f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add the three new values to ``lesson_block_type`` and create
    the six backing child tables (3 draft + 3 release). PG 12+
    supports ``ALTER TYPE ... ADD VALUE`` inside a transaction;
    the rest of the migration commits in the same tx.
    """
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'single_choice'",
    )
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'multi_choice'",
    )
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'text_input'",
    )

    # ------------------------ draft tables ------------------------ #

    op.create_table(
        "single_choice_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("options", JSONB, nullable=False),
        sa.Column("correct_option_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "multi_choice_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("options", JSONB, nullable=False),
        sa.Column("correct_option_ids", JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "text_input_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("accepted_answers", JSONB, nullable=False),
        sa.Column(
            "case_sensitive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "trim_whitespace",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        "course_release_single_choice_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("options", JSONB, nullable=False),
        sa.Column("correct_option_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "course_release_multi_choice_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("options", JSONB, nullable=False),
        sa.Column("correct_option_ids", JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "course_release_text_input_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("accepted_answers", JSONB, nullable=False),
        sa.Column(
            "case_sensitive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "trim_whitespace",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
    enum without the three new values after deleting any rows
    that use them on both the draft and snapshot sides.
    """
    for value in ("single_choice", "multi_choice", "text_input"):
        op.execute(f"DELETE FROM course_release_blocks WHERE type = '{value}'")
        op.execute(f"DELETE FROM lesson_blocks WHERE type = '{value}'")

    op.drop_table("course_release_text_input_blocks")
    op.drop_table("course_release_multi_choice_blocks")
    op.drop_table("course_release_single_choice_blocks")
    op.drop_table("text_input_blocks")
    op.drop_table("multi_choice_blocks")
    op.drop_table("single_choice_blocks")

    op.execute("ALTER TYPE lesson_block_type RENAME TO lesson_block_type_old")
    op.execute(
        "CREATE TYPE lesson_block_type AS ENUM "
        "('html', 'katex', 'rutube_video', 'code')",
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
