from collections.abc import AsyncIterator
from typing import Protocol

from learnic.application.common.collaboration.events import ContentEvent
from learnic.entities.product.ids import ProductID


class ContentEventBus(Protocol):
    """Pub/sub channel for collaborative course-content edits.

    Producers (mutation command handlers) publish a
    :class:`ContentEvent` after the request transaction commits,
    so subscribers never see an event for a rolled-back mutation.

    Consumers (the course-content WebSocket endpoint) iterate
    ``subscribe(product_id)`` and forward events to the
    connected clients of that product.

    Implementations must work across multiple FastAPI processes —
    Author A on process 1 makes a change; Author B subscribed on
    process 2 must observe it.
    """

    async def publish(self, event: ContentEvent) -> None:
        """Broadcast ``event`` to every active subscriber of its product."""

    def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator[ContentEvent]:
        """Open a fresh subscription stream for one product.

        The returned iterator yields events for that product as they
        arrive and releases the underlying subscription on
        ``aclose()`` / when the consumer stops iterating.
        """
