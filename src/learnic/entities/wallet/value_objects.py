from learnic.entities.common.value_object import ValueObject
from learnic.entities.wallet.constants import (
    IDEMPOTENCY_KEY_MAX_LEN,
    MAX_AMOUNT,
)
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.errors import (
    InvalidAmountError,
    InvalidIdempotencyKeyError,
)


class MinorAmount(ValueObject):
    """A non-negative sum in the minimal unit of a currency.

    For RUB this is kopecks: ``1.50 RUB`` is stored as
    ``MinorAmount(150)``. Floats are never used — every arithmetic
    operation stays in integer space, removing rounding surprises.
    Upper bound :data:`MAX_AMOUNT` guards against typos and overflow.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidAmountError("negative")
        if self.value > MAX_AMOUNT:
            raise InvalidAmountError("too_large")


class Money(ValueObject):
    """A :class:`MinorAmount` paired with the currency it is denominated in.

    Embedded into entities (e.g. ``Product.price``) via SQLAlchemy
    ``composite()``. Two ``Money`` values are not arithmetically
    combinable in this code — currency conversion is intentionally
    out of scope until multi-currency wallets ship.

    ``__composite_values__`` is overridden to flatten the inner
    :class:`MinorAmount` into its raw ``int`` so SQLAlchemy can write
    it directly to a ``BigInteger`` column without going through the
    VO type (the default implementation would hand SQLAlchemy a
    ``MinorAmount`` instance, which the column does not understand).
    """

    amount: MinorAmount
    currency: Currency

    def __composite_values__(self) -> tuple[object, ...]:
        return (self.amount.value, self.currency)


class IdempotencyKey(ValueObject):
    """A short opaque token that uniquely identifies an externally-triggered operation.

    Used on :class:`learnic.entities.wallet.models.LedgerEntry` to make
    credit/debit safe against retries from external systems (admin
    tools, payment-provider webhooks). Internal events that the system
    itself drives — release-of-freeze, freeze-creation — leave this
    field ``None``; they are made idempotent by entity state instead.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidIdempotencyKeyError("empty")
        if len(self.value) > IDEMPOTENCY_KEY_MAX_LEN:
            raise InvalidIdempotencyKeyError("too_long")
