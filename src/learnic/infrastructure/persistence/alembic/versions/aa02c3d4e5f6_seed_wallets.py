"""seed user and platform wallets

Backfills a RUB ``Wallet`` row for every existing user — without
this, users created before the wallet feature shipped would not
be able to receive any credit or to spend, and the FK on
``orders.student_id`` would still resolve but the purchase
handler would raise ``WalletNotFoundError``.

Also inserts the singleton platform wallet (one row per currency,
``owner_kind='platform'``, ``user_id IS NULL``). The partial-unique
index ``uq_wallets_platform_currency`` guards against a second
insert in any future migration or hand-fix.

``gen_random_uuid()`` is provided by core PostgreSQL ≥13 — no
``pgcrypto`` / ``uuid-ossp`` extension required.

Revision ID: aa02c3d4e5f6
Revises: aa01b2c3d4e5
Create Date: 2026-05-14 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "aa02c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "aa01b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade data."""
    op.execute(
        "INSERT INTO wallets (oid, owner_kind, user_id, currency, available_amount) "
        "SELECT gen_random_uuid(), 'user', oid, 'RUB', 0 FROM users",
    )
    op.execute(
        "INSERT INTO wallets (oid, owner_kind, user_id, currency, available_amount) "
        "VALUES (gen_random_uuid(), 'platform', NULL, 'RUB', 0)",
    )


def downgrade() -> None:
    """Downgrade data."""
    op.execute("DELETE FROM wallets")
