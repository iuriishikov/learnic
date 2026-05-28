"""add product_gifts and gift notification subtype tables

Creates the ``product_gifts`` aggregate (gift of product/course
access to a user, accepted or declined by the recipient with a
14-day TTL) plus the three ``notification_gift_*`` subtype tables
that back the gift notification kinds. Split from ``giftk0001``
because PostgreSQL refuses to use the freshly-added enum values in
the same transaction they were created in.

Revision ID: giftt0002
Revises: giftk0001
Create Date: 2026-05-25 00:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "giftt0002"
down_revision: Union[str, Sequence[str], None] = "giftk0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Full current value set of the reused ``notification_kind`` enum.
_NOTIFICATION_KIND = postgresql.ENUM(
    "invite_sent",
    "invite_accepted",
    "invite_declined",
    "access_revoked",
    "new_login",
    "storage_quota_warning",
    "storage_quota_enforced",
    "gift_received",
    "gift_accepted",
    "gift_declined",
    name="notification_kind",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "product_gifts",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=True),
        sa.Column("invited_email", sa.String(length=320), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending_invite",
                "accepted",
                "declined",
                "revoked",
                name="product_gift_status",
            ),
            nullable=False,
        ),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column(
            "invite_token_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "invite_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "declined_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "invite_token_hash",
            name="uq_gift_invite_token_hash",
        ),
    )
    op.create_index(
        "ix_gift_recipient_id",
        "product_gifts",
        ["recipient_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_gift_product_recipient_active "
        "ON product_gifts (product_id, recipient_id) "
        "WHERE recipient_id IS NOT NULL "
        "AND status NOT IN ('revoked', 'declined')",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_gift_product_email_pending "
        "ON product_gifts (product_id, invited_email) "
        "WHERE invited_email IS NOT NULL "
        "AND status = 'pending_invite'",
    )

    op.create_table(
        "notification_gift_received",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _NOTIFICATION_KIND, nullable=False),
        sa.Column("gift_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_gift_received_parent",
        ),
        sa.ForeignKeyConstraint(
            ["gift_id"],
            ["product_gifts.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'gift_received'",
            name="ck_notif_gift_received_kind",
        ),
    )

    op.create_table(
        "notification_gift_accepted",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _NOTIFICATION_KIND, nullable=False),
        sa.Column("gift_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_gift_accepted_parent",
        ),
        sa.ForeignKeyConstraint(
            ["gift_id"],
            ["product_gifts.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'gift_accepted'",
            name="ck_notif_gift_accepted_kind",
        ),
    )

    op.create_table(
        "notification_gift_declined",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _NOTIFICATION_KIND, nullable=False),
        sa.Column("gift_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("decliner_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_gift_declined_parent",
        ),
        sa.ForeignKeyConstraint(
            ["gift_id"],
            ["product_gifts.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decliner_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'gift_declined'",
            name="ck_notif_gift_declined_kind",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the subtype tables and ``product_gifts`` (its indexes go
    with it), then the ``product_gift_status`` enum. The gift
    ``notification_kind`` values are preserved — Postgres cannot drop
    enum members without rewriting every dependent row.
    """
    op.drop_table("notification_gift_declined")
    op.drop_table("notification_gift_accepted")
    op.drop_table("notification_gift_received")
    op.drop_table("product_gifts")
    op.execute("DROP TYPE IF EXISTS product_gift_status")
