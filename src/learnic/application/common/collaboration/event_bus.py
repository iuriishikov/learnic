"""Pub/sub Protocol alias for the course-content collaboration channel.

Concretises :class:`~learnic.application.common.events.EventChannel`
to the channel's payload union so handlers can depend on
``ContentEventBus`` without re-stating the type parameter.
"""

from typing import TypeAlias

from learnic.application.common.collaboration.payloads import ContentPayload
from learnic.application.common.events import EventChannel

ContentEventBus: TypeAlias = EventChannel[ContentPayload]
