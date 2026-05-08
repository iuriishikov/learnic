from datetime import datetime, timezone
from typing import Any

from learnic.application.common.product_collaboration_events.event_bus import (
    CollaborationEventBus,
)
from learnic.application.common.product_collaboration_events.events import (
    CollaborationEvent,
    CollaborationEventKind,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def publish_collaboration_event(
    bus: CollaborationEventBus,
    *,
    kind: CollaborationEventKind,
    product_id: ProductID,
    actor_id: UserID,
    payload: dict[str, Any],
) -> None:
    """Build a :class:`CollaborationEvent` with ``occurred_at`` and publish.

    Always called **after** ``transaction.commit()`` so a rolled-back
    invite / accept / revoke never publishes.
    """
    await bus.publish(
        CollaborationEvent(
            kind=kind,
            product_id=product_id,
            actor_id=actor_id,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        ),
    )


__all__ = [
    "CollaborationEvent",
    "CollaborationEventBus",
    "CollaborationEventKind",
    "publish_collaboration_event",
]
