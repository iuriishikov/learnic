import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.order.purchase import (
    PurchaseConfig,
    PurchaseProductCommand,
    PurchaseProductCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.order.models import Order
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency, WalletOwnerKind
from learnic.entities.wallet.errors import (
    InsufficientFundsError,
    PlatformWalletMissingError,
    ProductHasNoPriceError,
    WalletNotFoundError,
)
from learnic.entities.wallet.ids import WalletID
from learnic.entities.wallet.models import FreezeEntry, LedgerEntry, Wallet
from learnic.entities.product.value_objects import ProductPriceAmount
from learnic.entities.wallet.value_objects import MinorAmount


def _make_product(price: ProductPriceAmount | None) -> Product:
    now = datetime.now(timezone.utc)
    product = Product(
        oid=ProductID(uuid.uuid4()),
        author_id=UserID(uuid.uuid4()),
        type=ProductType.COURSE,
        name=ProductTitle("Test"),
        status=ProductStatus.PUBLISHED,
        published_at=now,
        created_at=now,
        updated_at=now,
    )
    product.price = price
    return product


def _make_wallet(
    user_id: UserID | None,
    available: int,
    owner_kind: WalletOwnerKind = WalletOwnerKind.USER,
) -> Wallet:
    return Wallet(
        oid=WalletID(uuid.uuid4()),
        owner_kind=owner_kind,
        user_id=user_id,
        currency=Currency.RUB,
        available=MinorAmount(available),
    )


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fake_order_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fake_wallet_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def purchase_config() -> PurchaseConfig:
    return PurchaseConfig(
        sale_hold_ttl_seconds=14 * 24 * 3600,
        commission_hold_ttl_seconds=14 * 24 * 3600,
    )


@pytest.fixture
def handler(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_order_gateway: AsyncMock,
    fake_wallet_gateway: AsyncMock,
    purchase_config: PurchaseConfig,
) -> PurchaseProductCommandHandler:
    return PurchaseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        order_gateway=fake_order_gateway,
        wallet_gateway=fake_wallet_gateway,
        config=purchase_config,
    )


class TestPurchaseGoldenPath:
    @pytest.mark.asyncio
    async def test_splits_price_and_writes_full_event_set(
        self,
        handler: PurchaseProductCommandHandler,
        fake_transaction: AsyncMock,
        fake_entity_saver: MagicMock,
        fake_product_gateway: AsyncMock,
        fake_wallet_gateway: AsyncMock,
    ) -> None:
        student_id = UserID(uuid.uuid4())
        product = _make_product(ProductPriceAmount(500_00))
        student_wallet = _make_wallet(student_id, available=1000_00)
        author_wallet = _make_wallet(product.author_id, available=0)
        platform_wallet = _make_wallet(
            None, available=0, owner_kind=WalletOwnerKind.PLATFORM,
        )
        fake_product_gateway.with_id.return_value = product
        fake_wallet_gateway.for_user_locked.side_effect = [
            student_wallet,
            author_wallet,
        ]
        fake_wallet_gateway.platform_for_currency_locked.return_value = (
            platform_wallet
        )

        order_id = await handler.run(
            PurchaseProductCommand(
                student_id=student_id, product_id=product.oid,
            ),
        )

        # Student wallet debited by full price (10% commission, 90% to author).
        assert student_wallet.available.value == 500_00
        # Two FreezeEntry rows + one Order + three LedgerEntry rows = 6 saves.
        added: list[Any] = [
            call.args[0] for call in fake_entity_saver.add_one.call_args_list
        ]
        freezes = [e for e in added if isinstance(e, FreezeEntry)]
        orders = [e for e in added if isinstance(e, Order)]
        ledger = [e for e in added if isinstance(e, LedgerEntry)]
        assert len(freezes) == 2
        assert len(orders) == 1
        assert len(ledger) == 3
        # Author = 90% of price, platform = 10%.
        author_freeze = next(
            f for f in freezes if f.wallet_id == author_wallet.oid
        )
        platform_freeze = next(
            f for f in freezes if f.wallet_id == platform_wallet.oid
        )
        assert author_freeze.amount.value == 450_00
        assert platform_freeze.amount.value == 50_00
        assert orders[0].oid == order_id
        fake_transaction.commit.assert_awaited_once()


class TestPurchaseFailures:
    @pytest.mark.asyncio
    async def test_missing_product_raises(
        self,
        handler: PurchaseProductCommandHandler,
        fake_product_gateway: AsyncMock,
    ) -> None:
        fake_product_gateway.with_id.return_value = None
        with pytest.raises(EntityNotFoundError):
            await handler.run(
                PurchaseProductCommand(
                    student_id=UserID(uuid.uuid4()),
                    product_id=ProductID(uuid.uuid4()),
                ),
            )

    @pytest.mark.asyncio
    async def test_priceless_product_raises(
        self,
        handler: PurchaseProductCommandHandler,
        fake_product_gateway: AsyncMock,
    ) -> None:
        fake_product_gateway.with_id.return_value = _make_product(price=None)
        with pytest.raises(ProductHasNoPriceError):
            await handler.run(
                PurchaseProductCommand(
                    student_id=UserID(uuid.uuid4()),
                    product_id=ProductID(uuid.uuid4()),
                ),
            )

    @pytest.mark.asyncio
    async def test_missing_student_wallet_raises(
        self,
        handler: PurchaseProductCommandHandler,
        fake_product_gateway: AsyncMock,
        fake_wallet_gateway: AsyncMock,
    ) -> None:
        fake_product_gateway.with_id.return_value = _make_product(
            ProductPriceAmount(500_00),
        )
        fake_wallet_gateway.for_user_locked.return_value = None
        with pytest.raises(WalletNotFoundError):
            await handler.run(
                PurchaseProductCommand(
                    student_id=UserID(uuid.uuid4()),
                    product_id=ProductID(uuid.uuid4()),
                ),
            )

    @pytest.mark.asyncio
    async def test_missing_platform_wallet_raises(
        self,
        handler: PurchaseProductCommandHandler,
        fake_product_gateway: AsyncMock,
        fake_wallet_gateway: AsyncMock,
    ) -> None:
        student_id = UserID(uuid.uuid4())
        product = _make_product(ProductPriceAmount(500_00))
        fake_product_gateway.with_id.return_value = product
        fake_wallet_gateway.for_user_locked.side_effect = [
            _make_wallet(student_id, 1000_00),
            _make_wallet(product.author_id, 0),
        ]
        fake_wallet_gateway.platform_for_currency_locked.return_value = None
        with pytest.raises(PlatformWalletMissingError):
            await handler.run(
                PurchaseProductCommand(
                    student_id=student_id, product_id=product.oid,
                ),
            )

    @pytest.mark.asyncio
    async def test_insufficient_funds_propagates_from_wallet(
        self,
        handler: PurchaseProductCommandHandler,
        fake_product_gateway: AsyncMock,
        fake_wallet_gateway: AsyncMock,
    ) -> None:
        student_id = UserID(uuid.uuid4())
        product = _make_product(ProductPriceAmount(500_00))
        fake_product_gateway.with_id.return_value = product
        fake_wallet_gateway.for_user_locked.side_effect = [
            _make_wallet(student_id, available=100_00),
            _make_wallet(product.author_id, available=0),
        ]
        fake_wallet_gateway.platform_for_currency_locked.return_value = (
            _make_wallet(None, 0, WalletOwnerKind.PLATFORM)
        )
        with pytest.raises(InsufficientFundsError):
            await handler.run(
                PurchaseProductCommand(
                    student_id=student_id, product_id=product.oid,
                ),
            )
