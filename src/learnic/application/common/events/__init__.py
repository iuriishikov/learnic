"""Generic per-product event channel primitives.

A WebSocket-backed event channel — the abstraction that powers
both the course-content channel
(:mod:`learnic.application.common.collaboration`) and the
product-metadata channel
(:mod:`learnic.application.common.product_events`) — is fully
captured here:

* :class:`Event` — the generic envelope (typed payload +
  ``product_id`` scope + ``actor_id`` + timestamp).
* :class:`EventChannel` — the generic publish/subscribe Protocol;
  one channel per product.
* :func:`publish_event` — the standard "build envelope, publish
  after-commit" helper.

Concrete channels (content, product) plug in by setting
``TPayload`` to their closed payload union. The :class:`KIND`
class-attribute on each payload dataclass is the wire
discriminator; the Redis adapter (in
:mod:`learnic.infrastructure.events`) reads it via
``type(payload).KIND`` so payloads stay free of repeated
``kind: Literal[...]`` fields.
"""

from learnic.application.common.events.channel import (
    EventChannel,
    HasPayloadKind,
)
from learnic.application.common.events.events import Event
from learnic.application.common.events.publisher import publish_event

__all__ = [
    "Event",
    "EventChannel",
    "HasPayloadKind",
    "publish_event",
]
