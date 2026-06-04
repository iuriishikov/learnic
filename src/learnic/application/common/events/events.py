"""Generic event envelope shared by per-product WS channels.

:class:`Event` is parameterised by its payload type so the wire
contract is closed at the type level — each channel binds
``TPayload`` to its own discriminated union (e.g.
``Event[ContentPayload]``, ``Event[ProductPayload]``).

The scope is :class:`ProductID` for every current channel; that
matches the Redis routing convention (``<channel>:<product_id>``)
and the WebSocket route shape (``/products/{id}/events``,
``/notes/{id}/events``). If a future channel ever wants a
different scope, generalise this dataclass with a second
``TScope`` parameter at that point — not before.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

TPayload = TypeVar("TPayload")


@dataclass(slots=True, frozen=True)
class Event(Generic[TPayload]):
    """A single event published to a per-product channel.

    ``payload`` carries the type-specific data; its
    ``KIND`` class attribute is the wire discriminator
    (extracted at serialisation time, not stored on the instance).
    ``product_id`` routes the event to subscribers of one product;
    ``actor_id`` is the user who caused the mutation;
    ``occurred_at`` is set by :func:`publish_event` immediately
    after the request transaction commits.
    """

    payload: TPayload
    product_id: ProductID
    actor_id: UserID
    occurred_at: datetime
