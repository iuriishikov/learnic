"""add partial index for the unverified-user purge

The abandoned-unverified purge
(``UserMapperAlchemy.delete_abandoned_unverified``) and the on-demand
reclaim during re-registration
(``delete_abandoned_unverified_by_email``) both filter
``users WHERE email_verified IS false``. With the purge now running
every 15 minutes (was daily), a full sequential scan of ``users`` on
every tick is wasteful as the table grows. This partial index lets the
planner enumerate just the (typically tiny) unverified subset.

The predicate is written ``email_verified IS false`` to match the
``ColumnElement`` the ORM emits (``email_verified.is_(False)``) exactly,
so Postgres can prove the partial index applies to the purge query.
``oid`` is the indexed column because the purge's two ``NOT EXISTS``
subqueries correlate on ``users.oid``.

Revision ID: purgeidx0001
Revises: relcollage0001
Create Date: 2026-06-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "purgeidx0001"
down_revision: Union[str, Sequence[str], None] = "relcollage0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the partial index over unverified users."""
    op.create_index(
        "ix_users_unverified",
        "users",
        ["oid"],
        unique=False,
        postgresql_where=sa.text("email_verified IS false"),
    )


def downgrade() -> None:
    """Drop the partial index over unverified users."""
    op.drop_index(
        "ix_users_unverified",
        table_name="users",
        postgresql_where=sa.text("email_verified IS false"),
    )
