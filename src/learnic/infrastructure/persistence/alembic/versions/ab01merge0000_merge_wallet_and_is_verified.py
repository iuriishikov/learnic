"""merge wallet and is_verified heads

Two independent migration branches were live in the repo before
this point:

* ``a1b8cde6f7a0`` (``add_users_is_verified``) branched off
  ``b1c2d3e4f5a7`` and was never folded back into the main chain.
* ``aa02c3d4e5f6`` (``seed_wallets``) is the tail of the
  wallet/order feature shipped on top of ``z0a7bcd5e6f7``.

Both heads need to be applied for the DB schema to match the
mapped SQLAlchemy models (``users.is_verified`` on one side, the
wallet/order tables and ``products.price_*`` on the other). This
revision is the topological merge — no DDL, just a single parent
pointer that unifies the chain so ``alembic upgrade head``
resolves to one revision again.

Revision ID: ab01merge0000
Revises: a1b8cde6f7a0, aa02c3d4e5f6
Create Date: 2026-05-16 00:00:00.000000

"""

from typing import Sequence, Union

revision: str = "ab01merge0000"
down_revision: Union[str, Sequence[str], None] = (
    "a1b8cde6f7a0",
    "aa02c3d4e5f6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
