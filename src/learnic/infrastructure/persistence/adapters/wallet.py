from datetime import datetime
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.wallet import (
    FreezeEntryGateway,
    LedgerEntryGateway,
    LedgerEntryView,
    LedgerReader,
    WalletGateway,
    WalletReader,
    WalletView,
)
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import (
    Currency,
    FreezeStatus,
    LedgerKind,
    WalletOwnerKind,
)
from learnic.entities.wallet.ids import (
    FreezeEntryID,
    LedgerEntryID,
    WalletID,
)
from learnic.entities.wallet.models import FreezeEntry, LedgerEntry, Wallet
from learnic.infrastructure.persistence.models.wallet import (
    freeze_entries_table,
    ledger_entries_table,
    wallets_table,
)


class WalletMapperAlchemy(WalletGateway):
    """Persistence-side gateway for :class:`Wallet`.

    ``*_locked`` variants emit ``SELECT ... FOR UPDATE`` so the caller
    can mutate ``available`` without racing concurrent purchases or the
    release worker writing to the same row.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: WalletID) -> Wallet | None:
        stmt = sa.select(Wallet).where(wallets_table.c.oid == oid)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def with_id_locked(self, oid: WalletID) -> Wallet | None:
        stmt = (
            sa.select(Wallet)
            .where(wallets_table.c.oid == oid)
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def for_user(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> Wallet | None:
        stmt = sa.select(Wallet).where(
            wallets_table.c.user_id == user_id,
            wallets_table.c.currency == currency,
            wallets_table.c.owner_kind == WalletOwnerKind.USER,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def for_user_locked(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> Wallet | None:
        stmt = (
            sa.select(Wallet)
            .where(
                wallets_table.c.user_id == user_id,
                wallets_table.c.currency == currency,
                wallets_table.c.owner_kind == WalletOwnerKind.USER,
            )
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def platform_for_currency(
        self,
        currency: Currency,
    ) -> Wallet | None:
        stmt = sa.select(Wallet).where(
            wallets_table.c.currency == currency,
            wallets_table.c.owner_kind == WalletOwnerKind.PLATFORM,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def platform_for_currency_locked(
        self,
        currency: Currency,
    ) -> Wallet | None:
        stmt = (
            sa.select(Wallet)
            .where(
                wallets_table.c.currency == currency,
                wallets_table.c.owner_kind == WalletOwnerKind.PLATFORM,
            )
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class FreezeEntryMapperAlchemy(FreezeEntryGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: FreezeEntryID) -> FreezeEntry | None:
        stmt = sa.select(FreezeEntry).where(
            freeze_entries_table.c.oid == oid,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def with_id_locked(
        self,
        oid: FreezeEntryID,
    ) -> FreezeEntry | None:
        stmt = (
            sa.select(FreezeEntry)
            .where(freeze_entries_table.c.oid == oid)
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def ripe_locked(
        self,
        before: datetime,
        limit: int,
    ) -> list[FreezeEntry]:
        # SKIP LOCKED so two scheduler ticks racing on the same batch
        # divide work instead of blocking each other; ORDER BY
        # unfreeze_at means the oldest-pending row goes first.
        stmt = (
            sa.select(FreezeEntry)
            .where(
                freeze_entries_table.c.status == FreezeStatus.FROZEN,
                freeze_entries_table.c.unfreeze_at <= before,
            )
            .order_by(freeze_entries_table.c.unfreeze_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self._session.execute(stmt)).scalars())


class LedgerEntryMapperAlchemy(LedgerEntryGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_idempotency_key(
        self,
        key: str,
    ) -> LedgerEntry | None:
        stmt = sa.select(LedgerEntry).where(
            ledger_entries_table.c.idempotency_key == key,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class WalletReaderAlchemy(WalletReader):
    """Read-side adapter computing ``pending`` on the fly.

    A scalar subquery aggregates frozen-status freeze entries for the
    target wallet — one round-trip, one consistent snapshot of
    available + pending. There is no denormalised pending column that
    could drift from the underlying freezes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_user(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> WalletView | None:
        pending_subq = (
            sa.select(
                sa.func.coalesce(sa.func.sum(freeze_entries_table.c.amount), 0),
            )
            .where(
                freeze_entries_table.c.wallet_id == wallets_table.c.oid,
                freeze_entries_table.c.status == FreezeStatus.FROZEN,
            )
            .scalar_subquery()
        )
        stmt = sa.select(
            wallets_table.c.oid,
            wallets_table.c.owner_kind,
            wallets_table.c.user_id,
            wallets_table.c.currency,
            wallets_table.c.available_amount,
            pending_subq.label("pending"),
        ).where(
            wallets_table.c.user_id == user_id,
            wallets_table.c.currency == currency,
            wallets_table.c.owner_kind == WalletOwnerKind.USER,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return WalletView(
            oid=WalletID(row.oid),
            owner_kind=WalletOwnerKind(row.owner_kind),
            user_id=UserID(row.user_id) if row.user_id is not None else None,
            currency=Currency(row.currency),
            available=int(row.available_amount),
            pending=int(row.pending),
        )


class LedgerReaderAlchemy(LedgerReader):
    """Implementation of :class:`LedgerReader`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def paginated_for_wallet(
        self,
        wallet_id: WalletID,
        pagination: Pagination,
    ) -> list[LedgerEntryView]:
        stmt = (
            sa.select(
                ledger_entries_table.c.oid,
                ledger_entries_table.c.kind,
                ledger_entries_table.c.delta,
                ledger_entries_table.c.reference_id,
                ledger_entries_table.c.created_at,
            )
            .where(ledger_entries_table.c.wallet_id == wallet_id)
            .order_by(sa.desc(ledger_entries_table.c.created_at))
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            LedgerEntryView(
                oid=LedgerEntryID(row.oid),
                kind=LedgerKind(row.kind),
                delta=int(row.delta),
                reference_id=row.reference_id,
                created_at=row.created_at,
            )
            for row in rows
        ]
