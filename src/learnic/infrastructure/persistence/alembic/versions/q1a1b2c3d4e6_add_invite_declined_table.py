"""add notification_invite_declined subtype table

Adds the per-kind subtype table for the ``invite_declined``
notification — sent to the inviter when the recipient declines
a pending invite in-app. Carries the collaboration / product
references plus ``decliner_id`` so the panel can render the
declining user's avatar without an extra fetch and offer a
"re-invite" CTA tied to the source collaboration.

Mirrors the option B persistence shape used by
``notification_invite_sent`` and ``notification_invite_accepted``:
composite ``(notification_id, kind)`` foreign key against
``notifications`` plus a CHECK constraint pinning the subtype to
its kind, so a row of the wrong kind cannot attach.

Split from the parent enum migration (``p0a1b2c3d4e5``) because
PostgreSQL refuses to use a freshly-added enum value inside the
same transaction it was created in.

Revision ID: q1a1b2c3d4e6
Revises: p0a1b2c3d4e5
Create Date: 2026-05-10 10:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "q1a1b2c3d4e6"
down_revision: Union[str, Sequence[str], None] = "p0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_invite_declined",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "invite_sent",
                "invite_accepted",
                "invite_declined",
                name="notification_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("collaboration_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("decliner_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_invite_declined_parent",
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
            ["decliner_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.CheckConstraint(
            "kind = 'invite_declined'",
            name="ck_notif_invite_declined_kind",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the subtype table. The ``invite_declined`` enum value
    itself is preserved — Postgres cannot drop enum members
    without rewriting every dependent row, and the parent
    migration documents the intentional asymmetry.
    """
    op.drop_table("notification_invite_declined")
