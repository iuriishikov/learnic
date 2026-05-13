"""Generic post-commit publish helper for per-product event channels."""

from datetime import datetime, timezone
from typing import TypeVar

from learnic.application.common.events.channel import EventChannel
from learnic.application.common.events.events import Event
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

TPayload = TypeVar("TPayload")


async def publish_event(
    channel: EventChannel[TPayload],
    *,
    payload: TPayload,
    product_id: ProductID,
    actor_id: UserID,
) -> None:
    """Build an :class:`Event` with ``occurred_at`` and publish.

    Thin helper so handlers don't repeat the timestamp + envelope
    construction in every mutation. Always called **after**
    ``transaction.commit()`` so a rolled-back command never
    publishes.
    """
    await channel.publish(
        Event(
            payload=payload,
            product_id=product_id,
            actor_id=actor_id,
            occurred_at=datetime.now(timezone.utc),
        ),
    )
