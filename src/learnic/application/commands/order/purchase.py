from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.order import OrderGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.wallet import WalletGateway
from learnic.entities.order.ids import OrderID
from learnic.entities.order.models import Order
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.constants import (
    COMMISSION_PERMILLE_DENOMINATOR,
    PLATFORM_COMMISSION_PERMILLE,
)
from learnic.entities.wallet.enums import Currency, FreezeSource, LedgerKind
from learnic.entities.wallet.errors import (
    PlatformWalletMissingError,
    ProductHasNoPriceError,
    WalletNotFoundError,
)
from learnic.entities.wallet.models import FreezeEntry, LedgerEntry
from learnic.entities.wallet.value_objects import MinorAmount, Money


@dataclass(slots=True, frozen=True)
class PurchaseProductCommand:
    student_id: UserID
    product_id: ProductID


@dataclass(slots=True, frozen=True)
class PurchaseConfig:
    """Refund-window TTLs in seconds.

    Both shares of a purchase are frozen until their ``unfreeze_at``
    passes — typically 14 days. Using separate TTLs for ``SALE_HOLD``
    and ``COMMISSION_HOLD`` is deliberate: if accounting later wants
    the platform's cut to settle on a different cadence than the
    author's payout, the policy already supports it.
    """

    sale_hold_ttl_seconds: int
    commission_hold_ttl_seconds: int


@final
class PurchaseProductCommandHandler:
    """Move money from student to author + platform on purchase.

    Steps, all inside one transaction:

    1. Load the product; reject if its ``price`` is unset.
    2. Lock the student wallet, author wallet and platform wallet
       in that order (a fixed lock order avoids deadlocks between
       concurrent purchases involving the same pair of users).
    3. Split price into commission (per-mille of price, integer
       floor) and author share. Floor-rounding favours the author
       on fractional kopecks.
    4. Debit the student's available balance — raises
       ``InsufficientFundsError`` when the wallet cannot cover the
       price.
    5. Freeze both shares on the author / platform wallets via
       ``FreezeEntry``; ``unfreeze_at`` is materialised from the
       configured TTL so the release worker does not need policy
       awareness.
    6. Persist the ``Order`` referencing both freezes and snapshot
       the price + commission for audit.
    7. Append three ledger entries (``PURCHASE`` on the student,
       ``FREEZE`` on author and platform — the FREEZE rows carry
       ``delta=0`` because the money is now on FreezeEntry, not
       on ``available``).
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        order_gateway: OrderGateway,
        wallet_gateway: WalletGateway,
        config: PurchaseConfig,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._order_gateway: Final = order_gateway
        self._wallet_gateway: Final = wallet_gateway
        self._config: Final = config

    async def run(self, data: PurchaseProductCommand) -> OrderID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.price is None:
            raise ProductHasNoPriceError

        # Products no longer store currency — the buyer's account
        # currency is the source of truth. RUB-only at this phase;
        # re-source from ``User.currency`` when multi-currency lands.
        price_amount_value = product.price.value
        price_currency = Currency.RUB
        price_amount = MinorAmount(price_amount_value)
        price = Money(price_amount, price_currency)
        commission_value = (
            price_amount_value * PLATFORM_COMMISSION_PERMILLE
        ) // COMMISSION_PERMILLE_DENOMINATOR
        author_share_value = price_amount_value - commission_value

        student_wallet = await self._wallet_gateway.for_user_locked(
            data.student_id,
            price_currency,
        )
        if student_wallet is None:
            raise WalletNotFoundError
        author_wallet = await self._wallet_gateway.for_user_locked(
            product.author_id,
            price_currency,
        )
        if author_wallet is None:
            raise WalletNotFoundError
        platform_wallet = await self._wallet_gateway.platform_for_currency_locked(
            price_currency,
        )
        if platform_wallet is None:
            raise PlatformWalletMissingError(currency=price_currency.value)

        # Single now() shared across every event in this transaction so
        # ledger timestamps and freeze windows line up exactly.
        now = datetime.now(timezone.utc)
        sale_unfreeze = now + timedelta(
            seconds=self._config.sale_hold_ttl_seconds,
        )
        commission_unfreeze = now + timedelta(
            seconds=self._config.commission_hold_ttl_seconds,
        )

        student_wallet.debit_available(price_amount)

        author_freeze = FreezeEntry.create(
            wallet_id=author_wallet.oid,
            amount=MinorAmount(author_share_value),
            source=FreezeSource.SALE_HOLD,
            frozen_at=now,
            unfreeze_at=sale_unfreeze,
        )
        platform_freeze = FreezeEntry.create(
            wallet_id=platform_wallet.oid,
            amount=MinorAmount(commission_value),
            source=FreezeSource.COMMISSION_HOLD,
            frozen_at=now,
            unfreeze_at=commission_unfreeze,
        )
        order = Order.create(
            student_id=data.student_id,
            product_id=data.product_id,
            price=price,
            commission_amount=MinorAmount(commission_value),
            author_freeze_id=author_freeze.oid,
            platform_freeze_id=platform_freeze.oid,
            created_at=now,
        )
        self._entity_saver.add_one(author_freeze)
        self._entity_saver.add_one(platform_freeze)
        self._entity_saver.add_one(order)
        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=student_wallet.oid,
                delta=-price_amount_value,
                kind=LedgerKind.PURCHASE,
                reference_id=order.oid,
                created_at=now,
            ),
        )
        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=author_wallet.oid,
                delta=0,
                kind=LedgerKind.FREEZE,
                reference_id=author_freeze.oid,
                created_at=now,
            ),
        )
        self._entity_saver.add_one(
            LedgerEntry.of(
                wallet_id=platform_wallet.oid,
                delta=0,
                kind=LedgerKind.FREEZE,
                reference_id=platform_freeze.oid,
                created_at=now,
            ),
        )
        await self._transaction.commit()
        return order.oid
