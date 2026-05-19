from learnic.entities.common.errors import DomainError


class OrderAlreadyRefundedError(DomainError):
    """Order is already in ``REFUNDED`` state."""


class RefundWindowClosedError(DomainError):
    """Refund window has closed — at least one freeze for this order is no longer frozen."""


class OrderActorMismatchError(DomainError):
    """The acting user is not the student who owns this order."""
