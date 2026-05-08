from collections.abc import AsyncIterator
from typing import Protocol

from learnic.application.common.presence.events import PresenceEvent


class PresenceEventBus(Protocol):
    """Pub/sub channel for cross-process presence change notifications.

    Producers (``PresenceTracker``) publish edge-transition events;
    consumers (the WebSocket handler) iterate ``subscribe()`` and
    forward relevant events to subscribed clients.

    Implementations must work across multiple FastAPI processes — a
    user connecting on process A and a friend subscribed on process B
    must both observe the same event stream.
    """

    async def publish(self, event: PresenceEvent) -> None:
        """Broadcast ``event`` to every active subscriber."""

    def subscribe(self) -> AsyncIterator[PresenceEvent]:
        """Open a fresh subscription stream.

        The returned iterator yields events as they arrive and releases
        the underlying subscription on ``aclose()`` / when the consumer
        stops iterating. Each call produces an independent stream — do
        not share one iterator between coroutines.
        """
