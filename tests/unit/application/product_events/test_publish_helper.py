import uuid
from unittest.mock import AsyncMock

from learnic.application.common.product_events import (
    ProductEvent,
    ProductEventKind,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def test_publish_product_event_builds_and_forwards() -> None:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    product_id = ProductID(uuid.uuid4())
    actor_id = UserID(uuid.uuid4())

    await publish_product_event(
        bus,
        kind=ProductEventKind.NAME_CHANGED,
        product_id=product_id,
        actor_id=actor_id,
        payload={"name": "new"},
    )

    bus.publish.assert_awaited_once()
    event: ProductEvent = bus.publish.call_args.args[0]
    assert isinstance(event, ProductEvent)
    assert event.kind is ProductEventKind.NAME_CHANGED
    assert event.product_id == product_id
    assert event.actor_id == actor_id
    assert event.payload == {"name": "new"}
    assert event.occurred_at is not None
