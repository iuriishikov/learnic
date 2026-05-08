from datetime import datetime, timezone
from typing import Any

from learnic.application.common.collaboration.event_bus import (
    ContentEventBus,
)
from learnic.application.common.collaboration.events import (
    ContentEvent,
    ContentEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def publish_content_event(
    bus: ContentEventBus,
    *,
    kind: ContentEventKind,
    product_id: ProductID,
    actor_id: UserID,
    payload: dict[str, Any],
) -> None:
    """Build a :class:`ContentEvent` with ``occurred_at`` and publish.

    Thin helper so handlers don't repeat the timestamp + dataclass
    construction in every mutation. Always called **after**
    ``transaction.commit()`` so a rolled-back command never
    publishes.
    """
    await bus.publish(
        ContentEvent(
            kind=kind,
            product_id=product_id,
            actor_id=actor_id,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        ),
    )


__all__ = [
    "ContentEvent",
    "ContentEventBus",
    "ContentEventKind",
    "publish_content_event",
]
