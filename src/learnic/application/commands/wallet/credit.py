from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.wallet import (
    LedgerEntryGateway,
    WalletGateway,
)
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency, LedgerKind
from learnic.entities.wallet.errors import WalletNotFoundError
from learnic.entities.wallet.ids import LedgerEntryID
from learnic.entities.wallet.models import LedgerEntry
from learnic.entities.wallet.value_objects import IdempotencyKey, MinorAmount


@dataclass(slots=True, frozen=True)
class CreditWalletCommand:
    """Credit ``amount`` minor units to ``user_id``'s wallet in ``currency``.

    ``source`` describes why the credit happened — typical values are
    ``LedgerKind.TOPUP`` (admin or payment-provider topup),
    ``LedgerKind.REFUND`` (return of money) or ``LedgerKind.ADJUSTMENT``
    (saппорт correction). The kind goes straight into the resulting
    ledger entry for audit.

    ``idempotency_key`` MUST be set when the caller is an external
    boundary (admin tools, payment-provider webhook) that may retry.
    If the same key is seen twice the second call is a no-op and
    returns the original ledger entry id.
    """

    user_id: UserID
    amount: int
    currency: Currency
    source: LedgerKind
    idempotency_key: str | None = None


@final
class CreditWalletCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        wallet_gateway: WalletGateway,
        ledger_gateway: LedgerEntryGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._wallet_gateway: Final = wallet_gateway
        self._ledger_gateway: Final = ledger_gateway

    async def run(self, data: CreditWalletCommand) -> LedgerEntryID:
        idempotency_key = (
            IdempotencyKey(data.idempotency_key)
            if data.idempotency_key is not None
            else None
        )
        if idempotency_key is not None:
            existing = await self._ledger_gateway.with_idempotency_key(
                idempotency_key.value,
            )
            if existing is not None:
                return existing.oid

        amount = MinorAmount(data.amount)
        wallet = await self._wallet_gateway.for_user_locked(
            data.user_id,
            data.currency,
        )
        if wallet is None:
            raise WalletNotFoundError

        wallet.credit_available(amount)

        now = datetime.now(timezone.utc)
        entry = LedgerEntry.of(
            wallet_id=wallet.oid,
            delta=data.amount,
            kind=data.source,
            reference_id=None,
            created_at=now,
            idempotency_key=idempotency_key.value if idempotency_key else None,
        )
        self._entity_saver.add_one(entry)
        await self._transaction.commit()
        return entry.oid
