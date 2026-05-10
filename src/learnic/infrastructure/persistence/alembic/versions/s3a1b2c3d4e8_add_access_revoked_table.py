"""add notification_access_revoked subtype table

Per-kind subtype table for the ``access_revoked`` notification —
sent to a user whose **active** collaboration was kicked. Carries
the collaboration / product references plus ``revoker_id`` so the
panel can render who removed access. Pending-invite revocations
are not covered here; they surface on the recipient's existing
``invite_sent`` card via the snapshot republish.

Mirrors the option B persistence shape used by the other
``notification_*`` subtype tables: composite ``(notification_id,
kind)`` foreign key + CHECK constraint pinning the subtype to its
kind so a row of the wrong kind cannot attach.

Split from the parent enum migration (``r2a1b2c3d4e7``) because
PostgreSQL refuses to use a freshly-added enum value inside the
same transaction it was created in.

Revision ID: s3a1b2c3d4e8
Revises: r2a1b2c3d4e7
Create Date: 2026-05-10 14:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "s3a1b2c3d4e8"
down_revision: Union[str, Sequence[str], None] = "r2a1b2c3d4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_access_revoked",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "invite_sent",
                "invite_accepted",
                "invite_declined",
                "access_revoked",
                name="notification_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("collaboration_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("revoker_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_access_revoked_parent",
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
            ["revoker_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'access_revoked'",
            name="ck_notif_access_revoked_kind",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the subtype table. The ``access_revoked`` enum value
    itself is preserved — Postgres cannot drop enum members
    without rewriting every dependent row.
    """
    op.drop_table("notification_access_revoked")
