from collections.abc import AsyncIterator
from typing import Protocol

from learnic.application.common.product_events.events import ProductEvent
from learnic.entities.product.ids import ProductID


class ProductEventBus(Protocol):
    """Pub/sub channel for product-level edits.

    Producers (product / Q&A command handlers) publish a
    :class:`ProductEvent` after the request transaction commits,
    so subscribers never see an event for a rolled-back mutation.

    Consumers (the product WebSocket endpoint) iterate
    ``subscribe(product_id)`` and forward events to the connected
    clients of that product.

    Implementations must work across multiple FastAPI processes —
    Author A on process 1 makes a change; Author B subscribed on
    process 2 must observe it.
    """

    async def publish(self, event: ProductEvent) -> None:
        """Broadcast ``event`` to every active subscriber of its product."""

    def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[ProductEvent]:
        """Open a fresh subscription stream for one product.

        The returned iterator yields events for that product as they
        arrive and releases the underlying subscription on
        ``aclose()`` / when the consumer stops iterating.
        """
