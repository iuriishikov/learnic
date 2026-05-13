import uuid
from unittest.mock import AsyncMock

from learnic.application.common.events import Event
from learnic.application.common.product_events import (
    NameChangedPayload,
    ProductEvent,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def test_publish_product_event_builds_and_forwards() -> None:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    product_id = ProductID(uuid.uuid4())
    actor_id = UserID(uuid.uuid4())
    payload = NameChangedPayload(name="new")

    await publish_product_event(
        bus,
        payload=payload,
        product_id=product_id,
        actor_id=actor_id,
    )

    bus.publish.assert_awaited_once()
    event: ProductEvent = bus.publish.call_args.args[0]
    assert isinstance(event, Event)
    assert event.payload is payload
    assert type(event.payload).KIND == "name_changed"
    assert event.product_id == product_id
    assert event.actor_id == actor_id
    assert event.occurred_at is not None
