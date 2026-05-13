"""Redis-backed adapter for the course-content collaboration channel.

Thin subclass of :class:`RedisEventChannel` parameterised by the
channel's :data:`ContentPayload` union and the
``payload_from_wire`` dispatch from
:mod:`learnic.application.common.collaboration.payloads`. All
serialisation, subscription, and lifecycle logic lives on the
generic base.
"""

from typing import Any, ClassVar

from typing_extensions import override

from learnic.application.common.collaboration.payloads import (
    ContentPayload,
    payload_from_wire,
)
from learnic.infrastructure.events import RedisEventChannel


class ContentEventBusRedis(RedisEventChannel[ContentPayload]):
    CHANNEL_PREFIX: ClassVar[str] = "content"

    @override
    def _payload_from_wire(
        self,
        kind: str,
        data: dict[str, Any],
    ) -> ContentPayload:
        return payload_from_wire(kind, data)
