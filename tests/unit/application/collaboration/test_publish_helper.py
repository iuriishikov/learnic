import uuid
from unittest.mock import AsyncMock

from learnic.application.common.collaboration import (
    ContentEvent,
    ContentEventKind,
    publish_content_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


async def test_publish_content_event_builds_and_forwards() -> None:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    product_id = ProductID(uuid.uuid4())
    actor_id = UserID(uuid.uuid4())

    await publish_content_event(
        bus,
        kind=ContentEventKind.MODULE_RENAMED,
        product_id=product_id,
        actor_id=actor_id,
        payload={"module_id": "abc", "title": "x"},
    )

    bus.publish.assert_awaited_once()
    event: ContentEvent = bus.publish.call_args.args[0]
    assert isinstance(event, ContentEvent)
    assert event.kind is ContentEventKind.MODULE_RENAMED
    assert event.product_id == product_id
    assert event.actor_id == actor_id
    assert event.payload == {"module_id": "abc", "title": "x"}
    assert event.occurred_at is not None
