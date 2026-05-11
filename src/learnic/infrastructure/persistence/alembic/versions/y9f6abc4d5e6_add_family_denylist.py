"""add family_denylist for instant access-token revocation

Stateless access JWTs cannot be revoked by themselves — they live
out their natural ``exp``. The ``token_denylist`` covers per-jti
revocations (logout-this-device, password change), but it cannot
catch access tokens of *other* sessions when a family is revoked
("Logout from this device" CTA on the new-login security card):
the revoker doesn't have the suspect device's access jti to
denylist.

This migration adds a sibling ``family_denylist`` keyed by the
refresh-token ``family_id``. Access JWTs now carry the
``family_id`` they were minted for; the auth path checks the
family-level denylist and rejects every access token belonging
to a revoked family on the next request — no 20-minute grace
window. Entries auto-expire at ``access_ttl`` past the revocation
moment because no token issued earlier can still be valid by
then.

Revision ID: y9f6abc4d5e6
Revises: x8e5fab3c4d5
Create Date: 2026-05-10 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "y9f6abc4d5e6"
down_revision: Union[str, Sequence[str], None] = "x8e5fab3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "family_denylist",
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("family_id"),
    )
    op.create_index(
        "ix_family_denylist_expires",
        "family_denylist",
        ["expires_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_family_denylist_expires",
        table_name="family_denylist",
    )
    op.drop_table("family_denylist")
