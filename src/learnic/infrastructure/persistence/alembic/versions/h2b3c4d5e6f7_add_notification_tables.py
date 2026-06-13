"""add in-app notification tables

Adds the base ``notifications`` table plus a subtype table per
:class:`NotificationKind` (option B persistence). The composite
``(notification_id, kind)`` foreign key prevents subtype rows
from attaching to a parent of the wrong ``kind``.

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-05-08 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "h2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "g1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "invite_sent",
                "invite_accepted",
                name="notification_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "invites",
                "files",
                "jobs",
                "other",
                name="notification_category",
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "oid",
            "kind",
            name="uq_notifications_oid_kind",
        ),
    )
    op.create_index(
        "ix_notif_recipient_created",
        "notifications",
        ["recipient_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_notif_recipient_category_created",
        "notifications",
        ["recipient_id", "category", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE INDEX ix_notif_recipient_unread "
        "ON notifications (recipient_id) "
        "WHERE read_at IS NULL",
    )

    op.create_table(
        "notification_invite_sent",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "invite_sent",
                "invite_accepted",
                name="notification_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("collaboration_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_invite_sent_parent",
        ),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["product_collaborations.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'invite_sent'",
            name="ck_notif_invite_sent_kind",
        ),
    )

    op.create_table(
        "notification_invite_accepted",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "invite_sent",
                "invite_accepted",
                name="notification_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("collaboration_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("collaborator_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_invite_accepted_parent",
        ),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["product_collaborations.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["collaborator_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'invite_accepted'",
            name="ck_notif_invite_accepted_kind",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("notification_invite_accepted")
    op.drop_table("notification_invite_sent")
    op.drop_index("ix_notif_recipient_unread", table_name="notifications")
    op.drop_index(
        "ix_notif_recipient_category_created",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notif_recipient_created",
        table_name="notifications",
    )
    op.drop_table("notifications")
    op.execute("DROP TYPE notification_category")
    op.execute("DROP TYPE notification_kind")
