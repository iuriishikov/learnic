"""add files table and user avatar/cover FKs

Revision ID: b3e9a72c51ff
Revises: a7c1f2d8b401
Create Date: 2026-04-22 02:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3e9a72c51ff"
down_revision: Union[str, Sequence[str], None] = "a7c1f2d8b401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "files",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False),
        sa.Column("bucket", sa.String(length=63), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.oid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index(
        "ix_files_uploaded_by_active",
        "files",
        ["uploaded_by"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_files_deleted_at",
        "files",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    op.add_column(
        "users",
        sa.Column("avatar_file_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("cover_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_avatar_file_id",
        "users",
        "files",
        ["avatar_file_id"],
        ["oid"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_cover_file_id",
        "users",
        "files",
        ["cover_file_id"],
        ["oid"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_users_cover_file_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_avatar_file_id", "users", type_="foreignkey")
    op.drop_column("users", "cover_file_id")
    op.drop_column("users", "avatar_file_id")

    op.drop_index("ix_files_deleted_at", table_name="files")
    op.drop_index("ix_files_uploaded_by_active", table_name="files")
    op.drop_table("files")
