from enum import StrEnum


class Currency(StrEnum):
    RUB = "RUB"


class WalletOwnerKind(StrEnum):
    USER = "user"
    PLATFORM = "platform"


class FreezeStatus(StrEnum):
    FROZEN = "frozen"
    RELEASED = "released"
    CANCELLED = "cancelled"


class FreezeSource(StrEnum):
    SALE_HOLD = "sale_hold"
    COMMISSION_HOLD = "commission_hold"


class LedgerKind(StrEnum):
    PURCHASE = "purchase"
    FREEZE = "freeze"
    RELEASE = "release"
    REFUND = "refund"
    CANCEL_FREEZE = "cancel_freeze"
    TOPUP = "topup"
    ADJUSTMENT = "adjustment"
