import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import (
    Currency,
    LedgerKind,
    WalletOwnerKind,
)
from learnic.entities.wallet.ids import (
    FreezeEntryID,
    LedgerEntryID,
    WalletID,
)
from learnic.entities.wallet.models import FreezeEntry, LedgerEntry, Wallet


@dataclass(slots=True, frozen=True)
class WalletView:
    """Read-side projection of a wallet with pending total already aggregated.

    ``available`` is the live ``Wallet.available`` column; ``pending``
    is computed on the fly by summing all ``FROZEN`` freeze entries
    that point at this wallet, so the two numbers always come from one
    consistent read of the DB without a denormalised cache to drift.
    """

    oid: WalletID
    owner_kind: WalletOwnerKind
    user_id: UserID | None
    currency: Currency
    available: int
    pending: int


@dataclass(slots=True, frozen=True)
class LedgerEntryView:
    """Read-side projection of a single ledger entry for history listings."""

    oid: LedgerEntryID
    kind: LedgerKind
    delta: int
    reference_id: uuid.UUID | None
    created_at: datetime


class WalletGateway(Protocol):
    """Write-side lookups for :class:`Wallet`.

    The ``*_locked`` variants emit ``SELECT ... FOR UPDATE`` so the
    caller can mutate ``available`` without racing concurrent
    purchases or worker releases targeting the same row.
    """

    async def with_id(self, oid: WalletID) -> Wallet | None: ...

    async def with_id_locked(self, oid: WalletID) -> Wallet | None: ...

    async def for_user(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> Wallet | None: ...

    async def for_user_locked(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> Wallet | None: ...

    async def platform_for_currency(
        self,
        currency: Currency,
    ) -> Wallet | None: ...

    async def platform_for_currency_locked(
        self,
        currency: Currency,
    ) -> Wallet | None: ...


class FreezeEntryGateway(Protocol):
    """Write-side lookups for :class:`FreezeEntry`."""

    async def with_id(self, oid: FreezeEntryID) -> FreezeEntry | None: ...

    async def with_id_locked(
        self,
        oid: FreezeEntryID,
    ) -> FreezeEntry | None: ...

    async def ripe_locked(
        self,
        before: datetime,
        limit: int,
    ) -> list[FreezeEntry]:
        """Return up to ``limit`` ``FROZEN`` entries with ``unfreeze_at <= before``.

        Rows are locked via ``FOR UPDATE SKIP LOCKED`` so multiple
        scheduler ticks running in parallel never process the same
        freeze twice; whichever tick grabbed a row keeps it for the
        duration of its transaction.
        """
        ...


class LedgerEntryGateway(Protocol):
    """Write-side lookups for :class:`LedgerEntry`.

    The single lookup exists to detect a duplicate external request via
    its ``idempotency_key`` before the unique-constraint at the DB
    layer raises. The constraint is the source of truth — this method
    is the convenient fast-path so callers can return a stable response.
    """

    async def with_idempotency_key(
        self,
        key: str,
    ) -> LedgerEntry | None: ...


class WalletReader(Protocol):
    """Read-side queries returning :class:`WalletView` projections."""

    async def for_user(
        self,
        user_id: UserID,
        currency: Currency,
    ) -> WalletView | None: ...


class LedgerReader(Protocol):
    """Read-side queries returning :class:`LedgerEntryView` projections."""

    async def paginated_for_wallet(
        self,
        wallet_id: WalletID,
        pagination: Pagination,
    ) -> list[LedgerEntryView]:
        """Return ledger entries for ``wallet_id`` ordered by ``created_at`` desc."""
        ...
