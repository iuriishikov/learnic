import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.wallet.credit import (
    CreditWalletCommand,
    CreditWalletCommandHandler,
)
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency, LedgerKind, WalletOwnerKind
from learnic.entities.wallet.errors import WalletNotFoundError
from learnic.entities.wallet.ids import LedgerEntryID, WalletID
from learnic.entities.wallet.models import LedgerEntry, Wallet
from learnic.entities.wallet.value_objects import MinorAmount


def _wallet(user_id: UserID, balance: int) -> Wallet:
    return Wallet(
        oid=WalletID(uuid.uuid4()),
        owner_kind=WalletOwnerKind.USER,
        user_id=user_id,
        currency=Currency.RUB,
        available=MinorAmount(balance),
    )


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_wallet_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fake_ledger_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_wallet_gateway: AsyncMock,
    fake_ledger_gateway: AsyncMock,
) -> CreditWalletCommandHandler:
    return CreditWalletCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        wallet_gateway=fake_wallet_gateway,
        ledger_gateway=fake_ledger_gateway,
    )


class TestCreditGoldenPath:
    @pytest.mark.asyncio
    async def test_credits_wallet_and_writes_ledger(
        self,
        handler: CreditWalletCommandHandler,
        fake_wallet_gateway: AsyncMock,
        fake_ledger_gateway: AsyncMock,
        fake_entity_saver: MagicMock,
        fake_transaction: AsyncMock,
    ) -> None:
        user_id = UserID(uuid.uuid4())
        wallet = _wallet(user_id, balance=0)
        fake_wallet_gateway.for_user_locked.return_value = wallet
        fake_ledger_gateway.with_idempotency_key.return_value = None

        await handler.run(
            CreditWalletCommand(
                user_id=user_id,
                amount=500_00,
                currency=Currency.RUB,
                source=LedgerKind.TOPUP,
            ),
        )

        assert wallet.available.value == 500_00
        added = fake_entity_saver.add_one.call_args.args[0]
        assert isinstance(added, LedgerEntry)
        assert added.delta == 500_00
        assert added.kind is LedgerKind.TOPUP
        fake_transaction.commit.assert_awaited_once()


class TestCreditIdempotency:
    @pytest.mark.asyncio
    async def test_returns_existing_entry_without_double_credit(
        self,
        handler: CreditWalletCommandHandler,
        fake_wallet_gateway: AsyncMock,
        fake_ledger_gateway: AsyncMock,
        fake_entity_saver: MagicMock,
        fake_transaction: AsyncMock,
    ) -> None:
        user_id = UserID(uuid.uuid4())
        existing_id = LedgerEntryID(uuid.uuid4())
        existing = MagicMock(oid=existing_id)
        fake_ledger_gateway.with_idempotency_key.return_value = existing

        result = await handler.run(
            CreditWalletCommand(
                user_id=user_id,
                amount=100,
                currency=Currency.RUB,
                source=LedgerKind.TOPUP,
                idempotency_key="payment-42",
            ),
        )

        assert result == existing_id
        fake_wallet_gateway.for_user_locked.assert_not_called()
        fake_entity_saver.add_one.assert_not_called()
        fake_transaction.commit.assert_not_called()


class TestCreditFailures:
    @pytest.mark.asyncio
    async def test_missing_wallet_raises(
        self,
        handler: CreditWalletCommandHandler,
        fake_wallet_gateway: AsyncMock,
        fake_ledger_gateway: AsyncMock,
    ) -> None:
        fake_ledger_gateway.with_idempotency_key.return_value = None
        fake_wallet_gateway.for_user_locked.return_value = None
        with pytest.raises(WalletNotFoundError):
            await handler.run(
                CreditWalletCommand(
                    user_id=UserID(uuid.uuid4()),
                    amount=100,
                    currency=Currency.RUB,
                    source=LedgerKind.TOPUP,
                ),
            )
