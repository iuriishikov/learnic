"""add note_block_answers (persisted learner submissions)

One row per ``(student, release block)``: a logged-in learner's
*latest* answer to an interactive block, upserted on
``(user_id, block_id)`` so their progress survives a reload — wrong
answers are stored too, so the SPA can restore the selection together
with the correct/incorrect verdict. The polymorphic submission lives
in a single ``JSONB`` ``payload`` column; correctness is stored
alongside. Rows are scoped to the pinned ``release_id`` and cascade
away with the user, the release, or the release block.

Column types are inlined (not imported from app constants) so the
migration is a self-contained snapshot of the schema at this revision.

Revision ID: nbansw0001
Revises: blgmeta0001
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "nbansw0001"
down_revision: Union[str, Sequence[str], None] = "blgmeta0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "note_block_answers",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.Uuid(), nullable=False),
        sa.Column("release_id", sa.Uuid(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
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
            ["user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["note_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["note_releases.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "user_id",
            "block_id",
            name="uq_note_block_answers_user_block",
        ),
    )
    op.create_index(
        "ix_note_block_answers_user_release",
        "note_block_answers",
        ["user_id", "release_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_note_block_answers_user_release",
        table_name="note_block_answers",
    )
    op.drop_table("note_block_answers")
