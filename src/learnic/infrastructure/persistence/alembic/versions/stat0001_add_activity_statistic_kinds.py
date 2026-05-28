"""add registration / enrollment / site_visit statistic kinds

Adds ``'registration'`` / ``'enrollment'`` / ``'site_visit'`` to the
``statistic_type`` enum so the subtype tables created by the next
migration (``stat0002``) can reference them. PostgreSQL refuses to use
a freshly-added enum value inside the same transaction it was created
in — same split rationale as the notification-kind additions
(``giftk0001`` → ``giftt0002``).

Revision ID: stat0001
Revises: admin0002
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "stat0001"
down_revision: Union[str, Sequence[str], None] = "admin0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE statistic_type ADD VALUE IF NOT EXISTS 'registration'",
    )
    op.execute(
        "ALTER TYPE statistic_type ADD VALUE IF NOT EXISTS 'enrollment'",
    )
    op.execute(
        "ALTER TYPE statistic_type ADD VALUE IF NOT EXISTS 'site_visit'",
    )


def downgrade() -> None:
    """No-op.

    PostgreSQL cannot drop an enum member without recreating the
    type. The companion migration drops the subtype tables that use
    these values, so by the time this one runs they are unused —
    leaving them in place is harmless.
    """
