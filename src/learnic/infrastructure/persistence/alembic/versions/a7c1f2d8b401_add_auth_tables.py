"""add auth tables

Revision ID: a7c1f2d8b401
Revises: e59dd55d967b
Create Date: 2026-04-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c1f2d8b401"
down_revision: Union[str, Sequence[str], None] = "e59dd55d967b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.oid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index(
        "ix_refresh_tokens_active_user",
        "refresh_tokens",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_refresh_tokens_family",
        "refresh_tokens",
        ["family_id"],
    )

    op.create_table(
        "email_tokens",
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.oid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_email_tokens_active",
        "email_tokens",
        ["user_id", "purpose"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )

    op.create_table(
        "signup_sessions",
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.oid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_signup_sessions_user",
        "signup_sessions",
        ["user_id"],
    )

    op.create_table(
        "token_denylist",
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(
        "ix_token_denylist_expires",
        "token_denylist",
        ["expires_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_token_denylist_expires", table_name="token_denylist")
    op.drop_table("token_denylist")

    op.drop_index("ix_signup_sessions_user", table_name="signup_sessions")
    op.drop_table("signup_sessions")

    op.drop_index("ix_email_tokens_active", table_name="email_tokens")
    op.drop_table("email_tokens")

    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_active_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
