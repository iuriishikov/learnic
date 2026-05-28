from collections.abc import AsyncIterator
from typing import Protocol

from learnic.application.common.cursors.events import CursorsEvent
from learnic.entities.product.ids import ProductID


class CursorsEventBus(Protocol):
    """Pub/sub channel for cross-process cursor-delta fanout.

    Producers (the cursors WS receive loop) publish a
    :class:`CursorsEvent` after each accepted client message and
    after each disconnect. Consumers (the cursors WS forward loop)
    subscribe per ``ProductID`` and yield only events for that
    product — the fanout is partitioned so a busy product doesn't
    spam unrelated channels.

    Implementations must work across multiple FastAPI processes —
    a client connecting on process A and another on process B must
    both observe the same stream for the same ``product_id``.
    """

    async def publish(self, event: CursorsEvent) -> None:
        """Broadcast ``event`` to every subscriber of its product."""

    def subscribe(self, product_id: ProductID) -> AsyncIterator[CursorsEvent]:
        """Open a fresh subscription stream for ``product_id``.

        The returned iterator yields events as they arrive and
        releases the underlying subscription on ``aclose()`` /
        when the consumer stops iterating. Each call produces an
        independent stream — do not share one iterator between
        coroutines.
        """
