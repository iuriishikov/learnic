from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.wallet import (
    FreezeEntryGateway,
    WalletGateway,
)
from learnic.entities.wallet.enums import LedgerKind
from learnic.entities.wallet.models import LedgerEntry
from learnic.entities.wallet.value_objects import MinorAmount

# Cap per tick so a single run never holds a giant lock set. The
# scheduler fires every minute, so any backlog drains within a few
# ticks even at this batch size.
BATCH_LIMIT: Final = 200


@final
class ReleaseRipeFreezesCommandHandler:
    """Release every freeze whose ``unfreeze_at`` has passed.

    Run by the scheduler tick every minute. Picks up to
    :data:`BATCH_LIMIT` rows with ``FOR UPDATE SKIP LOCKED`` so two
    overlapping ticks never touch the same freeze, releases each into
    its wallet's ``available`` balance, and writes a ``RELEASE``
    ledger entry per movement. Everything happens in one transaction
    so a partially-released batch never appears.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        wallet_gateway: WalletGateway,
        freeze_gateway: FreezeEntryGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._wallet_gateway: Final = wallet_gateway
        self._freeze_gateway: Final = freeze_gateway

    async def run(self) -> int:
        now = datetime.now(timezone.utc)
        ripe = await self._freeze_gateway.ripe_locked(
            before=now,
            limit=BATCH_LIMIT,
        )
        if not ripe:
            return 0
        for freeze in ripe:
            wallet = await self._wallet_gateway.with_id_locked(
                freeze.wallet_id,
            )
            if wallet is None:
                # Defensive: a wallet referenced by a freeze must exist —
                # the FK enforces it. If we still see None, skip the
                # freeze rather than crash the whole batch.
                continue
            wallet.credit_available(MinorAmount(freeze.amount.value))
            freeze.release(at=now)
            self._entity_saver.add_one(
                LedgerEntry.of(
                    wallet_id=wallet.oid,
                    delta=freeze.amount.value,
                    kind=LedgerKind.RELEASE,
                    reference_id=freeze.oid,
                    created_at=now,
                ),
            )
        await self._transaction.commit()
        return len(ripe)
