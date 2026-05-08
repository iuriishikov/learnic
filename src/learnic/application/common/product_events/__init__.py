from datetime import datetime, timezone
from typing import Any

from learnic.application.common.product_events.event_bus import (
    ProductEventBus,
)
from learnic.application.common.product_events.events import (
    ProductEvent,
    ProductEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def publish_product_event(
    bus: ProductEventBus,
    *,
    kind: ProductEventKind,
    product_id: ProductID,
    actor_id: UserID,
    payload: dict[str, Any],
) -> None:
    """Build a :class:`ProductEvent` with ``occurred_at`` and publish.

    Thin helper so handlers don't repeat the timestamp + dataclass
    construction in every mutation. Always called **after**
    ``transaction.commit()`` so a rolled-back command never
    publishes.
    """
    await bus.publish(
        ProductEvent(
            kind=kind,
            product_id=product_id,
            actor_id=actor_id,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        ),
    )


__all__ = [
    "ProductEvent",
    "ProductEventBus",
    "ProductEventKind",
    "publish_product_event",
]
