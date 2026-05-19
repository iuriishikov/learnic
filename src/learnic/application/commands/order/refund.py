from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.order import OrderGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.wallet import (
    FreezeEntryGateway,
    WalletGateway,
)
from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.errors import (
    OrderActorMismatchError,
    OrderAlreadyRefundedError,
    RefundWindowClosedError,
)
from learnic.entities.order.ids import OrderID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import FreezeStatus, LedgerKind
from learnic.entities.wallet.errors import WalletNotFoundError
from learnic.entities.wallet.models import LedgerEntry


@dataclass(slots=True, frozen=True)
class RefundPurchaseCommand:
    actor_id: UserID
    order_id: OrderID


@final
class RefundPurchaseCommandHandler:
    """Refund a paid order while both freezes are still pending.

    The refund window is implicit: it is open precisely as long as
    both the author's and platform's freeze entries are still in
    ``FROZEN`` state. Once either has been released by the worker
    the window is considered closed and refund is denied — the
    money is already in the author's / platform's available
    balance and cannot be clawed back from this handler.

    Only the student who placed the order can refund it. Auth is
    enforced by comparing ``actor_id`` to ``order.student_id``; no
    role lookup is needed because this is a self-action by the
    buyer (saппорт-initiated refunds will arrive in a separate
    command once admin tooling exists).
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        order_gateway: OrderGateway,
        freeze_gateway: FreezeEntryGateway,
        wallet_gateway: WalletGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._order_gateway: Final = order_gateway
        self._freeze_gateway: Final = freeze_gateway
        self._wallet_gateway: Final = wallet_gateway

    async def run(self, data: RefundPurchaseCommand) -> None:
        order = await self._order_gateway.with_id_locked(data.order_id)
        if order is None:
            raise EntityNotFoundError(data.order_id)
        if order.student_id != data.actor_id:
            raise OrderActorMismatchError
        if order.status is OrderStatus.REFUNDED:
            raise OrderAlreadyRefundedError

        author_freeze = await self._freeze_gateway.with_id_locked(
            order.author_freeze_id,
        )
        platform_freeze = await self._freeze_gateway.with_id_locked(
            order.platform_freeze_id,
        )
        if (
            author_freeze is None
            or platform_freeze is None
            or author_freeze.status is not FreezeStatus.FROZEN
            or platform_freeze.status is not FreezeStatus.FROZEN
        ):
            raise RefundWindowClosedError

        student_wallet = await self._wallet_gateway.for_user_locked(
            data.actor_id,
            order.price.currency,
        )
        if student_wallet is None:
            raise WalletNotFoundError

        now = datetime.now(timezone.utc)
        author_freeze.cancel(at=now)
        platform_freeze.cancel(at=now)
        student_wallet.credit_available(order.price.amount)
        order.mark_refunded(at=now)

        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=student_wallet.oid,
                delta=order.price.amount.value,
                kind=LedgerKind.REFUND,
                reference_id=order.oid,
                created_at=now,
            ),
        )
        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=author_freeze.wallet_id,
                delta=0,
                kind=LedgerKind.CANCEL_FREEZE,
                reference_id=author_freeze.oid,
                created_at=now,
            ),
        )
        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=platform_freeze.wallet_id,
                delta=0,
                kind=LedgerKind.CANCEL_FREEZE,
                reference_id=platform_freeze.oid,
                created_at=now,
            ),
        )
        await self._transaction.commit()
