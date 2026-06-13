"""add users.distribution_consent_at

Records the moment a user consents to the distribution of their
personal data under Article 10.1 of Federal Law 152-FZ (making profile
data publicly available). The consent is given via a separate, optional
checkbox on the registration form. ``NULL`` means no such consent is on
record; a future withdrawal flow clears the column back to ``NULL``.

Nullable with no server default: the column is set by the application
(``datetime.now(timezone.utc)``) only when the user ticks the box;
existing rows and opt-outs stay ``NULL``.

Revision ID: distconsent0001
Revises: trigrename0001
Create Date: 2026-06-13 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "distconsent0001"
down_revision: Union[str, Sequence[str], None] = "trigrename0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "distribution_consent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "distribution_consent_at")
