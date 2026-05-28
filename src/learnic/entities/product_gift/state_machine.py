"""State machine for :class:`ProductGift`.

Centralises the "which operation is allowed in which status" matrix
in one table (:data:`_ALLOWED_OPS`) instead of inline ``if
self.status in (...): raise`` guards across mutator methods. Adding
a new :class:`GiftStatus` means one new row here; missing rows fail
at import time, not in a runtime path.
"""

from enum import StrEnum
from typing import Final

from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.errors import (
    OperationNotAllowedInGiftStatusError,
)


class GiftOp(StrEnum):
    """Closed-set list of mutating operations on a gift."""

    ACCEPT = "accept"
    DECLINE = "decline"
    REVOKE = "revoke"


# Single source of truth for the state machine. Every status MUST
# appear here — see the import-time assertion below.
_ALLOWED_OPS: Final[dict[GiftStatus, frozenset[GiftOp]]] = {
    GiftStatus.PENDING_INVITE: frozenset(
        {
            GiftOp.ACCEPT,
            GiftOp.DECLINE,
            GiftOp.REVOKE,
        },
    ),
    GiftStatus.ACCEPTED: frozenset(),
    GiftStatus.DECLINED: frozenset(),
    GiftStatus.REVOKED: frozenset(),
}


# Fail-fast: any status without a row crashes at import time.
_missing_statuses = set(GiftStatus) - set(_ALLOWED_OPS)
if _missing_statuses:
    raise RuntimeError(
        "_ALLOWED_OPS is incomplete; missing entries for: "
        f"{sorted(s.value for s in _missing_statuses)}",
    )


def require_op(status: GiftStatus, op: GiftOp) -> None:
    """Raise if ``op`` is forbidden in ``status``."""
    if op not in _ALLOWED_OPS[status]:
        raise OperationNotAllowedInGiftStatusError(
            status=status.value,
            operation=op.value,
        )
