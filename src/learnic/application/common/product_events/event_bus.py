"""Pub/sub Protocol alias for the product-level WS channel."""

from typing import TypeAlias

from learnic.application.common.events import EventChannel
from learnic.application.common.product_events.payloads import ProductPayload

ProductEventBus: TypeAlias = EventChannel[ProductPayload]
