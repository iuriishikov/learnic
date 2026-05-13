"""Redis-backed adapter for the product-level WS channel.

Thin subclass of :class:`RedisEventChannel` parameterised by the
channel's :data:`ProductPayload` union and the
``payload_from_wire`` dispatch from
:mod:`learnic.application.common.product_events.payloads`. All
serialisation, subscription, and lifecycle logic lives on the
generic base.
"""

from typing import Any, ClassVar

from typing_extensions import override

from learnic.application.common.product_events.payloads import (
    ProductPayload,
    payload_from_wire,
)
from learnic.infrastructure.events import RedisEventChannel


class ProductEventBusRedis(RedisEventChannel[ProductPayload]):
    CHANNEL_PREFIX: ClassVar[str] = "product"

    @override
    def _payload_from_wire(
        self,
        kind: str,
        data: dict[str, Any],
    ) -> ProductPayload:
        return payload_from_wire(kind, data)
