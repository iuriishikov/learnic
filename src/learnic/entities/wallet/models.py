import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import (
    Currency,
    FreezeSource,
    FreezeStatus,
    LedgerKind,
    WalletOwnerKind,
)
from learnic.entities.wallet.errors import (
    FreezeAlreadyResolvedError,
    InsufficientFundsError,
)
from learnic.entities.wallet.ids import (
    FreezeEntryID,
    LedgerEntryID,
    WalletID,
)
from learnic.entities.wallet.value_objects import MinorAmount


@dataclass
class Wallet(BaseEntity[WalletID]):
    """A money holder — either a user's personal wallet or the platform wallet.

    Per ``(owner_kind, user_id, currency)`` there is at most one
    wallet: user wallets have non-``None`` ``user_id`` and a unique
    constraint on ``(user_id, currency)``; the platform wallet has
    ``user_id is None`` and there is exactly one row per currency.

    Only ``available`` is stored on the wallet; the pending (frozen)
    total is computed on the fly by aggregating
    :class:`FreezeEntry` rows so the wallet never carries a denormalised
    cache that could drift from the source of truth.
    """

    owner_kind: WalletOwnerKind
    user_id: UserID | None
    currency: Currency
    available: MinorAmount

    def credit_available(self, amount: MinorAmount) -> None:
        self.available = MinorAmount(self.available.value + amount.value)

    def debit_available(self, amount: MinorAmount) -> None:
        if self.available.value < amount.value:
            raise InsufficientFundsError(
                available=self.available.value,
                required=amount.value,
            )
        self.available = MinorAmount(self.available.value - amount.value)

    @classmethod
    def create_for_user(cls, user_id: UserID, currency: Currency) -> Self:
        return cls(
            oid=WalletID(uuid.uuid4()),
            owner_kind=WalletOwnerKind.USER,
            user_id=user_id,
            currency=currency,
            available=MinorAmount(0),
        )

    @classmethod
    def create_for_platform(cls, currency: Currency) -> Self:
        return cls(
            oid=WalletID(uuid.uuid4()),
            owner_kind=WalletOwnerKind.PLATFORM,
            user_id=None,
            currency=currency,
            available=MinorAmount(0),
        )


@dataclass
class FreezeEntry(BaseEntity[FreezeEntryID]):
    """A pending-money lot attached to a wallet.

    A freeze is created when an event needs a refund-protection window —
    today only the author's share (``SALE_HOLD``) and the platform's
    commission (``COMMISSION_HOLD``) at purchase time. After
    ``unfreeze_at`` passes, the release worker flips the status to
    ``RELEASED`` and credits :attr:`Wallet.available`. If a refund
    happens before then, the status flips to ``CANCELLED`` instead.

    ``unfreeze_at`` is materialised on creation from the configured
    TTL, so the worker only filters by date and is unaware of policy.
    """

    wallet_id: WalletID
    amount: MinorAmount
    source: FreezeSource
    status: FreezeStatus
    frozen_at: datetime
    unfreeze_at: datetime
    resolved_at: datetime | None

    def release(self, at: datetime) -> None:
        if self.status is not FreezeStatus.FROZEN:
            raise FreezeAlreadyResolvedError(current_status=self.status.value)
        self.status = FreezeStatus.RELEASED
        self.resolved_at = at

    def cancel(self, at: datetime) -> None:
        if self.status is not FreezeStatus.FROZEN:
            raise FreezeAlreadyResolvedError(current_status=self.status.value)
        self.status = FreezeStatus.CANCELLED
        self.resolved_at = at

    @classmethod
    def create(
        cls,
        wallet_id: WalletID,
        amount: MinorAmount,
        source: FreezeSource,
        frozen_at: datetime,
        unfreeze_at: datetime,
    ) -> Self:
        return cls(
            oid=FreezeEntryID(uuid.uuid4()),
            wallet_id=wallet_id,
            amount=amount,
            source=source,
            status=FreezeStatus.FROZEN,
            frozen_at=frozen_at,
            unfreeze_at=unfreeze_at,
            resolved_at=None,
        )


@dataclass
class LedgerEntry(BaseEntity[LedgerEntryID]):
    """An immutable journal record for every money-related event.

    ``delta`` is the signed change to the related wallet's ``available``
    in minor units. Informational events (``FREEZE``, ``CANCEL_FREEZE``)
    use ``delta=0``: they record what happened without changing
    ``available`` — the actual money sits on :class:`FreezeEntry`.

    ``reference_id`` points to the entity that caused the event —
    ``order_id`` for purchase/refund, ``freeze_entry_id`` for
    freeze/release/cancel, ``None`` for free-standing topups or
    adjustments.

    ``idempotency_key`` is set for entries originating outside the
    domain (admin credit, payment-provider webhooks). The DB enforces a
    unique constraint on it so retries from the outside cannot apply
    twice. Internal entries leave it ``None``; their idempotency comes
    from the originating entity's state machine.
    """

    wallet_id: WalletID
    delta: int
    kind: LedgerKind
    reference_id: uuid.UUID | None
    idempotency_key: str | None
    created_at: datetime

    @classmethod
    def of(
        cls,
        wallet_id: WalletID,
        delta: int,
        kind: LedgerKind,
        reference_id: uuid.UUID | None,
        created_at: datetime,
        idempotency_key: str | None = None,
    ) -> Self:
        return cls(
            oid=LedgerEntryID(uuid.uuid4()),
            wallet_id=wallet_id,
            delta=delta,
            kind=kind,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            created_at=created_at,
        )
