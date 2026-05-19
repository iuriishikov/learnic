"""add wallet, freeze_entries, ledger_entries, orders tables

Brings back the per-user money model after the temporary price drop
in ``a1c4d7f928b3``. Splits money out of products into wallets,
freezes the author's / platform's share until the refund window
closes, and journals every movement.

PG ENUMs are created explicitly so subsequent column declarations
(both in this migration and in the matching SQLAlchemy models) can
reference them with ``create_type=False`` — the standard idiom for
reusing PG types across tables without re-emitting ``CREATE TYPE``.

Revision ID: aa01b2c3d4e5
Revises: z0a7bcd5e6f7
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "aa01b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "z0a7bcd5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE TYPE currency AS ENUM ('RUB')")
    op.execute("CREATE TYPE wallet_owner_kind AS ENUM ('user', 'platform')")
    op.execute(
        "CREATE TYPE freeze_source AS ENUM ('sale_hold', 'commission_hold')",
    )
    op.execute(
        "CREATE TYPE freeze_status AS ENUM ('frozen', 'released', 'cancelled')",
    )
    op.execute(
        "CREATE TYPE ledger_kind AS ENUM ("
        "'purchase', 'freeze', 'release', 'refund', "
        "'cancel_freeze', 'topup', 'adjustment'"
        ")",
    )
    op.execute("CREATE TYPE order_status AS ENUM ('paid', 'refunded')")

    currency = postgresql.ENUM("RUB", name="currency", create_type=False)
    owner_kind = postgresql.ENUM(
        "user",
        "platform",
        name="wallet_owner_kind",
        create_type=False,
    )
    freeze_src = postgresql.ENUM(
        "sale_hold",
        "commission_hold",
        name="freeze_source",
        create_type=False,
    )
    freeze_st = postgresql.ENUM(
        "frozen",
        "released",
        "cancelled",
        name="freeze_status",
        create_type=False,
    )
    ledger_kind = postgresql.ENUM(
        "purchase",
        "freeze",
        "release",
        "refund",
        "cancel_freeze",
        "topup",
        "adjustment",
        name="ledger_kind",
        create_type=False,
    )
    order_st = postgresql.ENUM(
        "paid",
        "refunded",
        name="order_status",
        create_type=False,
    )

    op.create_table(
        "wallets",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("currency", currency, nullable=False),
        sa.Column(
            "available_amount",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.CheckConstraint(
            "available_amount >= 0",
            name="ck_wallets_available_non_negative",
        ),
    )
    op.create_index(
        "uq_wallets_user_currency",
        "wallets",
        ["user_id", "currency"],
        unique=True,
        postgresql_where=sa.text("owner_kind = 'user'"),
    )
    op.create_index(
        "uq_wallets_platform_currency",
        "wallets",
        ["currency"],
        unique=True,
        postgresql_where=sa.text("owner_kind = 'platform'"),
    )

    op.create_table(
        "freeze_entries",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("source", freeze_src, nullable=False),
        sa.Column("status", freeze_st, nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unfreeze_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet_id"], ["wallets.oid"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.CheckConstraint(
            "amount >= 0",
            name="ck_freeze_entries_amount_non_negative",
        ),
    )
    op.create_index(
        "ix_freeze_entries_ripe",
        "freeze_entries",
        ["unfreeze_at"],
        postgresql_where=sa.text("status = 'frozen'"),
    )
    op.create_index(
        "ix_freeze_entries_wallet_status",
        "freeze_entries",
        ["wallet_id", "status"],
    )

    op.create_table(
        "ledger_entries",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.BigInteger(), nullable=False),
        sa.Column("kind", ledger_kind, nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"], ["wallets.oid"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_ledger_entries_idempotency_key",
        ),
    )
    op.create_index(
        "ix_ledger_entries_wallet_created_desc",
        "ledger_entries",
        ["wallet_id", sa.text("created_at DESC")],
    )

    # Restore product price columns (dropped in a1c4d7f928b3) — now
    # nullable so DRAFT products without a set price still load.
    op.add_column(
        "products",
        sa.Column("price_amount", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("price_currency", currency, nullable=True),
    )
    op.create_check_constraint(
        "ck_products_price_pair",
        "products",
        "(price_amount IS NULL) = (price_currency IS NULL)",
    )
    op.create_check_constraint(
        "ck_products_price_non_negative",
        "products",
        "price_amount IS NULL OR price_amount >= 0",
    )

    op.create_table(
        "orders",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("price_amount", sa.BigInteger(), nullable=False),
        sa.Column("price_currency", currency, nullable=False),
        sa.Column("commission_amount", sa.BigInteger(), nullable=False),
        sa.Column("author_freeze_id", sa.Uuid(), nullable=False),
        sa.Column("platform_freeze_id", sa.Uuid(), nullable=False),
        sa.Column("status", order_st, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.oid"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.oid"], ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_freeze_id"],
            ["freeze_entries.oid"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["platform_freeze_id"],
            ["freeze_entries.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.CheckConstraint(
            "price_amount >= 0",
            name="ck_orders_price_non_negative",
        ),
        sa.CheckConstraint(
            "commission_amount >= 0",
            name="ck_orders_commission_non_negative",
        ),
        sa.CheckConstraint(
            "commission_amount <= price_amount",
            name="ck_orders_commission_le_price",
        ),
    )
    op.create_index(
        "ix_orders_student_created_desc",
        "orders",
        ["student_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_orders_student_created_desc", table_name="orders")
    op.drop_table("orders")

    op.drop_constraint(
        "ck_products_price_non_negative",
        "products",
        type_="check",
    )
    op.drop_constraint(
        "ck_products_price_pair",
        "products",
        type_="check",
    )
    op.drop_column("products", "price_currency")
    op.drop_column("products", "price_amount")

    op.drop_index(
        "ix_ledger_entries_wallet_created_desc",
        table_name="ledger_entries",
    )
    op.drop_table("ledger_entries")

    op.drop_index(
        "ix_freeze_entries_wallet_status",
        table_name="freeze_entries",
    )
    op.drop_index("ix_freeze_entries_ripe", table_name="freeze_entries")
    op.drop_table("freeze_entries")

    op.drop_index("uq_wallets_platform_currency", table_name="wallets")
    op.drop_index("uq_wallets_user_currency", table_name="wallets")
    op.drop_table("wallets")

    op.execute("DROP TYPE order_status")
    op.execute("DROP TYPE ledger_kind")
    op.execute("DROP TYPE freeze_status")
    op.execute("DROP TYPE freeze_source")
    op.execute("DROP TYPE wallet_owner_kind")
    op.execute("DROP TYPE currency")
