import pytest

from learnic.entities.wallet.constants import (
    IDEMPOTENCY_KEY_MAX_LEN,
    MAX_AMOUNT,
)
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.errors import (
    InvalidAmountError,
    InvalidIdempotencyKeyError,
)
from learnic.entities.wallet.value_objects import (
    IdempotencyKey,
    MinorAmount,
    Money,
)


class TestMinorAmount:
    def test_accepts_zero(self) -> None:
        assert MinorAmount(0).value == 0

    def test_accepts_positive(self) -> None:
        assert MinorAmount(150_00).value == 150_00

    def test_accepts_max(self) -> None:
        assert MinorAmount(MAX_AMOUNT).value == MAX_AMOUNT

    def test_rejects_negative(self) -> None:
        with pytest.raises(InvalidAmountError) as exc:
            MinorAmount(-1)
        assert exc.value.reason == "negative"

    def test_rejects_above_max(self) -> None:
        with pytest.raises(InvalidAmountError) as exc:
            MinorAmount(MAX_AMOUNT + 1)
        assert exc.value.reason == "too_large"


class TestMoney:
    def test_holds_amount_and_currency(self) -> None:
        money = Money(MinorAmount(500_00), Currency.RUB)
        assert money.amount.value == 500_00
        assert money.currency is Currency.RUB

    def test_composite_values_flattens_amount(self) -> None:
        money = Money(MinorAmount(150), Currency.RUB)
        # SQLAlchemy reads composite values via this hook; the inner
        # VO is unwrapped to a primitive so the BigInteger column
        # accepts it directly.
        amount, currency = money.__composite_values__()
        assert amount == 150
        assert currency is Currency.RUB


class TestIdempotencyKey:
    def test_accepts_valid(self) -> None:
        key = IdempotencyKey("payment-abc-123")
        assert key.value == "payment-abc-123"

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidIdempotencyKeyError) as exc:
            IdempotencyKey("")
        assert exc.value.reason == "empty"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidIdempotencyKeyError) as exc:
            IdempotencyKey("x" * (IDEMPOTENCY_KEY_MAX_LEN + 1))
        assert exc.value.reason == "too_long"
