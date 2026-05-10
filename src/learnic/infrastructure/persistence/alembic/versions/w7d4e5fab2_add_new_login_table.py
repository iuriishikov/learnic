"""add notification_new_login subtype table

Per-kind subtype table for the ``new_login`` security
notification — sent to a user whenever a successful login
lands on their account. Carries the device label / raw
User-Agent / IP captured at the HTTP boundary so the panel can
render "New login from Chrome on macOS" without an extra
fetch.

Mirrors the option B persistence shape used by the other
``notification_*`` subtype tables: composite ``(notification_id,
kind)`` foreign key + CHECK constraint pinning the subtype to
its kind so a row of the wrong kind cannot attach.

Split from the parent enum migration (``v6c3d4e5fab1``) because
PostgreSQL refuses to use a freshly-added enum value inside the
same transaction it was created in.

Revision ID: w7d4e5fab2
Revises: v6c3d4e5fab1
Create Date: 2026-05-10 16:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "w7d4e5fab2"
down_revision: Union[str, Sequence[str], None] = "v6c3d4e5fab1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_new_login",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "invite_sent",
                "invite_accepted",
                "invite_declined",
                "access_revoked",
                "new_login",
                name="notification_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("device_label", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_new_login_parent",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'new_login'",
            name="ck_notif_new_login_kind",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the subtype table. The ``new_login`` enum value itself
    is preserved — Postgres cannot drop enum members without
    rewriting every dependent row.
    """
    op.drop_table("notification_new_login")
