"""Event envelope alias for the product-level WS channel.

Fixes :class:`~learnic.application.common.events.Event` to the
channel-specific :data:`~learnic.application.common.product_events.payloads.ProductPayload`
union.
"""

from typing import TypeAlias

from learnic.application.common.events import Event
from learnic.application.common.product_events.payloads import ProductPayload

ProductEvent: TypeAlias = Event[ProductPayload]
