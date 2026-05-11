"""State machine for :class:`ProductCollaboration`.

Centralises the "which operation is allowed in which status" matrix
in one table (:data:`_ALLOWED_OPS`) instead of 5 inline ``if
self.status in (...): raise`` guards across mutator methods. Adding
a new :class:`CollaborationStatus` means one new row here; missing
rows fail at import time, not in a runtime path.
"""

from enum import StrEnum
from typing import Final

from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.errors import (
    OperationNotAllowedInStatusError,
)


class CollaborationOp(StrEnum):
    """Closed-set list of mutating operations on a collaboration."""

    ACCEPT = "accept"
    DECLINE = "decline"
    REVOKE = "revoke"
    REPLACE_GRANTS = "replace_grants"


# Single source of truth for the state machine. Every status MUST
# appear here — see the import-time assertion below.
_ALLOWED_OPS: Final[dict[CollaborationStatus, frozenset[CollaborationOp]]] = {
    CollaborationStatus.PENDING_INVITE: frozenset(
        {
            CollaborationOp.ACCEPT,
            CollaborationOp.DECLINE,
            CollaborationOp.REVOKE,
        },
    ),
    CollaborationStatus.ACTIVE: frozenset(
        {
            CollaborationOp.REVOKE,
            CollaborationOp.REPLACE_GRANTS,
        },
    ),
    CollaborationStatus.REVOKED: frozenset(),
    CollaborationStatus.DECLINED: frozenset(),
}


# Fail-fast: any status without a row crashes at import time.
_missing_statuses = set(CollaborationStatus) - set(_ALLOWED_OPS)
if _missing_statuses:
    raise RuntimeError(
        "_ALLOWED_OPS is incomplete; missing entries for: "
        f"{sorted(s.value for s in _missing_statuses)}",
    )


def require_op(
    status: CollaborationStatus,
    op: CollaborationOp,
) -> None:
    """Raise :class:`OperationNotAllowedInStatusError` if ``op`` is forbidden in ``status``."""
    if op not in _ALLOWED_OPS[status]:
        raise OperationNotAllowedInStatusError(
            status=status.value,
            operation=op.value,
        )
