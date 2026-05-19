from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.wallet.constants import IDEMPOTENCY_KEY_MAX_LEN
from learnic.entities.wallet.enums import (
    Currency,
    FreezeSource,
    FreezeStatus,
    LedgerKind,
    WalletOwnerKind,
)
from learnic.entities.wallet.models import FreezeEntry, LedgerEntry, Wallet
from learnic.entities.wallet.value_objects import MinorAmount
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Return ``.value``s of a ``StrEnum`` for ``sa.Enum.values_callable``.

    Mirrors the same helper in :mod:`product` — kept local so that
    each models module is independent (deletions never cascade
    through a shared helper module).
    """
    return [member.value for member in enum_cls]


# Shared PG ENUM type: every column that stores a currency points at the
# same backing PG type. ``sa.Enum`` is sufficient here — the type is
# created by the dedicated Alembic migration, not by metadata.create_all,
# and the Python-side dedup of identical Enum() instances at metadata
# level keeps DDL emission single-source.
currency_enum = sa.Enum(
    Currency,
    name="currency",
    values_callable=_enum_values,
)


wallets_table = sa.Table(
    "wallets",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "owner_kind",
        sa.Enum(
            WalletOwnerKind,
            name="wallet_owner_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "user_id",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column("currency", currency_enum, nullable=False),
    sa.Column(
        "available_amount",
        sa.BigInteger(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.CheckConstraint(
        "available_amount >= 0",
        name="ck_wallets_available_non_negative",
    ),
    # A user has at most one wallet per currency. Partial-unique so the
    # platform wallet (user_id IS NULL) is not constrained by this index.
    sa.Index(
        "uq_wallets_user_currency",
        "user_id",
        "currency",
        unique=True,
        postgresql_where=sa.text("owner_kind = 'user'"),
    ),
    # Exactly one platform wallet per currency.
    sa.Index(
        "uq_wallets_platform_currency",
        "currency",
        unique=True,
        postgresql_where=sa.text("owner_kind = 'platform'"),
    ),
)


freeze_entries_table = sa.Table(
    "freeze_entries",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "wallet_id",
        sa.Uuid,
        sa.ForeignKey("wallets.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("amount", sa.BigInteger(), nullable=False),
    sa.Column(
        "source",
        sa.Enum(
            FreezeSource,
            name="freeze_source",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "status",
        sa.Enum(
            FreezeStatus,
            name="freeze_status",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("unfreeze_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "amount >= 0",
        name="ck_freeze_entries_amount_non_negative",
    ),
    # Worker query: WHERE status='frozen' AND unfreeze_at <= :now
    # ORDER BY unfreeze_at — index supports both filter and order.
    sa.Index(
        "ix_freeze_entries_ripe",
        "unfreeze_at",
        postgresql_where=sa.text("status = 'frozen'"),
    ),
    # Pending-total reader: SUM(amount) WHERE wallet_id=? AND status='frozen'
    sa.Index(
        "ix_freeze_entries_wallet_status",
        "wallet_id",
        "status",
    ),
)


ledger_entries_table = sa.Table(
    "ledger_entries",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "wallet_id",
        sa.Uuid,
        sa.ForeignKey("wallets.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("delta", sa.BigInteger(), nullable=False),
    sa.Column(
        "kind",
        sa.Enum(
            LedgerKind,
            name="ledger_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column("reference_id", sa.Uuid, nullable=True),
    sa.Column(
        "idempotency_key",
        sa.String(IDEMPOTENCY_KEY_MAX_LEN),
        nullable=True,
        unique=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    # History listing: WHERE wallet_id=? ORDER BY created_at DESC
    sa.Index(
        "ix_ledger_entries_wallet_created_desc",
        "wallet_id",
        sa.desc("created_at"),
    ),
)


_wallet_mapped = False
_freeze_mapped = False
_ledger_mapped = False


def map_wallet_table() -> None:
    """Apply imperative mapping from :class:`Wallet` to ``wallets_table``."""
    global _wallet_mapped  # noqa: PLW0603
    if _wallet_mapped:
        return
    mapper_registry.map_imperatively(
        Wallet,
        wallets_table,
        properties={
            "oid": wallets_table.c.oid,
            "owner_kind": wallets_table.c.owner_kind,
            "user_id": wallets_table.c.user_id,
            "currency": wallets_table.c.currency,
            "available": composite(MinorAmount, wallets_table.c.available_amount),
        },
        column_prefix="_col_",
    )
    _wallet_mapped = True


def map_freeze_entry_table() -> None:
    """Apply imperative mapping from :class:`FreezeEntry`."""
    global _freeze_mapped  # noqa: PLW0603
    if _freeze_mapped:
        return
    mapper_registry.map_imperatively(
        FreezeEntry,
        freeze_entries_table,
        properties={
            "oid": freeze_entries_table.c.oid,
            "wallet_id": freeze_entries_table.c.wallet_id,
            "amount": composite(MinorAmount, freeze_entries_table.c.amount),
            "source": freeze_entries_table.c.source,
            "status": freeze_entries_table.c.status,
            "frozen_at": freeze_entries_table.c.frozen_at,
            "unfreeze_at": freeze_entries_table.c.unfreeze_at,
            "resolved_at": freeze_entries_table.c.resolved_at,
        },
        column_prefix="_col_",
    )
    _freeze_mapped = True


def map_ledger_entry_table() -> None:
    """Apply imperative mapping from :class:`LedgerEntry`.

    ``delta`` and ``reference_id`` map to plain columns — the entity
    already stores them as primitives. ``idempotency_key`` is plain
    too: VOs only wrap externally-supplied values during validation,
    after which the bare string travels through persistence.
    """
    global _ledger_mapped  # noqa: PLW0603
    if _ledger_mapped:
        return
    mapper_registry.map_imperatively(
        LedgerEntry,
        ledger_entries_table,
        properties={
            "oid": ledger_entries_table.c.oid,
            "wallet_id": ledger_entries_table.c.wallet_id,
            "delta": ledger_entries_table.c.delta,
            "kind": ledger_entries_table.c.kind,
            "reference_id": ledger_entries_table.c.reference_id,
            "idempotency_key": ledger_entries_table.c.idempotency_key,
            "created_at": ledger_entries_table.c.created_at,
        },
        column_prefix="_col_",
    )
    _ledger_mapped = True
