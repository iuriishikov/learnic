"""add storage_quota_warning / storage_quota_enforced enum values

Appends the two new labels to the ``notification_kind`` PG enum so
the companion migration can reference them from the subtype
tables' ``CHECK (kind = '...')`` constraints. Split from the
table-creation migration because PostgreSQL refuses to use a
freshly-added enum value inside the same transaction it was
created in — same rationale as the existing ``invite_declined`` /
``new_login`` enum migrations.

Files notifications opt-in lives on the existing ``push_files`` /
``email_files`` columns of ``notification_preferences`` — added
back when the FILES category was introduced — so no preference
columns are touched here.

Revision ID: s3breach0002
Revises: s2breach0001
Create Date: 2026-05-20 10:05:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "s3breach0002"
down_revision: Union[str, Sequence[str], None] = "s2breach0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Append new ``notification_kind`` enum values."""
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS "
        "'storage_quota_warning'",
    )
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS "
        "'storage_quota_enforced'",
    )


def downgrade() -> None:
    """No-op — ``ALTER TYPE … DROP VALUE`` does not exist in PG.

    Removing a label requires rebuilding the enum + rewriting every
    dependent row; the orphan labels are harmless until a future
    rebuild is desired.
    """
