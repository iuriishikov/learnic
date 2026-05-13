"""Generic publish/subscribe Protocol for per-product event channels.

:class:`EventChannel` is parametric in its payload union so each
concrete channel comes with a static contract — adding a new
``KIND`` to the union shows up in every subscriber's
``match payload:`` block via mypy.

Adapter implementations live in
:mod:`learnic.infrastructure.events`. The Protocol intentionally
exposes no implementation hooks (channel name, serialisation,
backplane) — those belong to the adapter, not the application
layer.
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar

from learnic.entities.product.ids import ProductID

if TYPE_CHECKING:
    from learnic.application.common.events.events import Event


class HasPayloadKind(Protocol):
    """Documents the implicit contract every channel payload satisfies.

    Each member of a channel's payload union declares a
    class-level ``KIND`` constant — a ``Literal[...]`` string
    that identifies the variant on the wire. Generic adapters
    read the discriminator via ``type(payload).KIND``.

    This Protocol is **not** used as the bound on :data:`TPayload`
    because mypy treats ``ClassVar`` invariantly and a payload
    union with per-variant ``Literal[...]`` ``KIND`` constants
    fails to satisfy a ``ClassVar[str]`` bound. The contract is
    enforced by convention and a runtime ``AttributeError`` if a
    payload lacks ``KIND`` at publish time.
    """

    KIND: ClassVar[str]


TPayload = TypeVar("TPayload")


class EventChannel(Protocol[TPayload]):
    """Pub/sub channel for per-product events of a single shape.

    Producers (mutation command handlers) call :meth:`publish`
    **after** ``transaction.commit()`` so subscribers never see
    an event for a rolled-back mutation. Consumers (the
    aggregate's WebSocket endpoint) iterate :meth:`subscribe`
    and forward events to the connected clients of that product.

    Implementations must work across multiple FastAPI processes:
    author A on process 1 makes a change; author B subscribed on
    process 2 must observe it.
    """

    async def publish(self, event: "Event[TPayload]") -> None:
        """Broadcast ``event`` to every active subscriber of its product."""

    def subscribe(
        self,
        product_id: ProductID,
    ) -> AsyncIterator["Event[TPayload]"]:
        """Open a fresh subscription stream for one product.

        The returned iterator yields events for that product as
        they arrive and releases the underlying subscription on
        ``aclose()`` / when the consumer stops iterating.
        """
