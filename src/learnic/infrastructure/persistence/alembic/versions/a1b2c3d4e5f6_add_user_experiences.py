"""add user_experiences table

Adds the ``user_experiences`` table backing the new per-user
work/study timeline entries. Owned by a user (CASCADE on parent
delete), optional icon stored as a soft-deletable file reference
(SET NULL on file delete to mirror the avatar / cover pattern).

Revision ID: a1b2c3d4e5f6
Revises: z0a7bcd5e6f7
Create Date: 2026-05-11 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z0a7bcd5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_experiences",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("icon_file_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["icon_file_id"],
            ["files.oid"],
            ondelete="SET NULL",
            use_alter=True,
            name="fk_user_experiences_icon_file_id",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_user_experiences_user_id_start_date",
        "user_experiences",
        ["user_id", sa.text("start_date DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_user_experiences_user_id_start_date",
        table_name="user_experiences",
    )
    op.drop_table("user_experiences")
