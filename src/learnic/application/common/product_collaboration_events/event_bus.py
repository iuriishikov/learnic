from collections.abc import AsyncIterator
from typing import Protocol

from learnic.application.common.product_collaboration_events.events import (
    CollaborationEvent,
)
from learnic.entities.product.ids import ProductID


class CollaborationEventBus(Protocol):
    """Pub/sub channel for collaboration-lifecycle deltas.

    Producers (collaboration command handlers) publish a
    :class:`CollaborationEvent` after the request transaction commits;
    consumers (the collaboration WebSocket endpoint) iterate
    ``subscribe(product_id)`` and forward events to the connected
    clients of that product.

    Implementations must work across multiple FastAPI processes —
    so a Moderator on process 1 issues an invite while Author on
    process 2 keeps a socket open and observes the delta.
    """

    async def publish(self, event: CollaborationEvent) -> None:
        """Broadcast ``event`` to every active subscriber of its product."""

    def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[CollaborationEvent]:
        """Open a fresh subscription stream for one product."""
