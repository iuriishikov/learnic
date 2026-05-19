from learnic.entities.common.errors import DomainError, FieldError


class InvalidAmountError(FieldError):
    """Raised when a :class:`MinorAmount` invariant is violated.

    ``reason`` is one of ``"negative"`` or ``"too_large"``.
    """

    reason: str


class InvalidIdempotencyKeyError(FieldError):
    """Raised when an :class:`IdempotencyKey` is empty or exceeds the length cap."""

    reason: str


class InsufficientFundsError(DomainError):
    """Wallet does not have enough available balance to cover a debit."""

    available: int
    required: int


class FreezeAlreadyResolvedError(DomainError):
    """The freeze entry is no longer ``frozen`` and cannot be released or cancelled."""

    current_status: str


class WalletNotFoundError(DomainError):
    """The wallet does not exist for the requested (owner, currency)."""


class PlatformWalletMissingError(DomainError):
    """No platform wallet exists for the given currency.

    The platform wallet is seeded by a data migration; this error
    indicates an environment-setup problem, not a user-facing failure.
    """

    currency: str


class ProductHasNoPriceError(DomainError):
    """The product is not for sale — its ``price`` is ``None``."""


class IdempotencyKeyConflictError(DomainError):
    """A ledger entry with the same idempotency key already exists."""

    key: str
