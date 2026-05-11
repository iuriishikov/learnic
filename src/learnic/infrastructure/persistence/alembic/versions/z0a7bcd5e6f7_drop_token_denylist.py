"""drop token_denylist (jti-level access-token denylist)

The jti-level denylist was only useful when the revoker could read
the suspect token's ``jti`` from a request cookie — i.e. self-logout
or self-revoke. Every revocation flow in the system now uses
``family_denylist`` (introduced in ``y9f6abc4d5e6``) which kills
**every** access JWT bound to the revoked refresh family, including
tokens on other devices the revoker cannot see. The jti table is
dead weight.

Revision ID: z0a7bcd5e6f7
Revises: y9f6abc4d5e6
Create Date: 2026-05-11 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "z0a7bcd5e6f7"
down_revision: Union[str, Sequence[str], None] = "y9f6abc4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(
        "ix_token_denylist_expires",
        table_name="token_denylist",
    )
    op.drop_table("token_denylist")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "token_denylist",
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(
        "ix_token_denylist_expires",
        "token_denylist",
        ["expires_at"],
    )
