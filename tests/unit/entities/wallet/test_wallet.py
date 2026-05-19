import uuid

import pytest

from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency, WalletOwnerKind
from learnic.entities.wallet.errors import InsufficientFundsError
from learnic.entities.wallet.models import Wallet
from learnic.entities.wallet.value_objects import MinorAmount


def _user_id() -> UserID:
    return UserID(uuid.uuid4())


class TestCreateForUser:
    def test_starts_with_zero_balance(self) -> None:
        wallet = Wallet.create_for_user(_user_id(), Currency.RUB)
        assert wallet.available.value == 0

    def test_marks_as_user_owned(self) -> None:
        user_id = _user_id()
        wallet = Wallet.create_for_user(user_id, Currency.RUB)
        assert wallet.owner_kind is WalletOwnerKind.USER
        assert wallet.user_id == user_id


class TestCreateForPlatform:
    def test_has_no_user_id(self) -> None:
        wallet = Wallet.create_for_platform(Currency.RUB)
        assert wallet.user_id is None

    def test_marks_as_platform_owned(self) -> None:
        wallet = Wallet.create_for_platform(Currency.RUB)
        assert wallet.owner_kind is WalletOwnerKind.PLATFORM


class TestCreditDebit:
    def test_credit_increases_balance(self) -> None:
        wallet = Wallet.create_for_user(_user_id(), Currency.RUB)
        wallet.credit_available(MinorAmount(100))
        wallet.credit_available(MinorAmount(50))
        assert wallet.available.value == 150

    def test_debit_decreases_balance(self) -> None:
        wallet = Wallet.create_for_user(_user_id(), Currency.RUB)
        wallet.credit_available(MinorAmount(500))
        wallet.debit_available(MinorAmount(300))
        assert wallet.available.value == 200

    def test_debit_exactly_available_leaves_zero(self) -> None:
        wallet = Wallet.create_for_user(_user_id(), Currency.RUB)
        wallet.credit_available(MinorAmount(500))
        wallet.debit_available(MinorAmount(500))
        assert wallet.available.value == 0

    def test_debit_above_available_raises(self) -> None:
        wallet = Wallet.create_for_user(_user_id(), Currency.RUB)
        wallet.credit_available(MinorAmount(100))
        with pytest.raises(InsufficientFundsError) as exc:
            wallet.debit_available(MinorAmount(200))
        assert exc.value.available == 100
        assert exc.value.required == 200
