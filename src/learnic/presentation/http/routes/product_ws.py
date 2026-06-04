"""Unified product WebSocket channel.

Read-only push of every per-product event for one product. Two
in-process buses fan in here:

* :class:`ProductEventBus` — product-metadata, cover, status,
  webinar defaults, Q&A, collaboration lifecycle, role catalogue.
* :class:`ContentEventBus` — note-content edits (modules,
  lessons, blocks, releases, draft reset). Only subscribed when
  the target product supports
  :attr:`ProductCapability.HAS_NOTE_CONTENT` — webinar products
  see product events only.

Both buses publish events that share the same wire envelope
(``Event[...]`` with ``payload.KIND`` discriminator), so the
multiplexed stream is a flat sequence of envelopes the SPA can
dispatch on ``kind`` alone. Cohorts (and their schedules /
sessions) are intentionally not covered yet.

Protocol summary (kept here, not in OpenAPI — OpenAPI 3 doesn't
model WebSockets):

* **Auth.** Standard ``accessCookie`` HttpOnly cookie sent by the
  browser on the WS handshake. Failure closes with code ``4401``
  before ``accept``.
* **Authorization.** Anyone with ``READ_PRODUCT`` on the target
  product can subscribe — that's the product owner (short-circuited
  by :class:`Authorizer`) plus any collaborator whose active
  grants include ``READ_PRODUCT`` (every editor / manager
  permission transitively grants it). Non-authorised callers get
  ``4403``.
* **Lifecycle.** Server pushes events one-way until the client
  disconnects. No client→server messages are interpreted yet.
* **Initial state.** Client refetches every REST resource the
  channel reflects (product, Q&A, collaborations, roles; for
  notes also the draft tree and releases) before opening the
  socket. On reconnect, refetch + resubscribe — no event
  buffering / replay.

Server → client message shape::

    {
      "kind": "<Payload.KIND>",     # e.g. "name_changed" or "module_added"
      "product_id": "<UUID>",
      "actor_id": "<UUID>",
      "payload": { ... },           # Payload-specific fields
      "occurred_at": "<ISO 8601>",
    }
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any, Final
from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.collaboration.event_bus import (
    ContentEventBus,
)
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    InvalidTokenError,
)
from learnic.application.common.events.events import Event
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.product_events.event_bus import (
    ProductEventBus,
)
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/products")


_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


@router.websocket("/{product_id}/events")
async def product_ws(
    websocket: WebSocket,
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """One-way push of every product / content event for a product.

    See module-level docstring for the full protocol.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return

        product_gateway = await request_scope.get(ProductGateway)
        product = await product_gateway.with_id(ProductID(product_id))
        if product is None:
            await websocket.close(code=4404, reason="product not found")
            return
        has_note_content = product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        )

        authorizer = await request_scope.get(Authorizer)
        try:
            await authorizer.require(
                ctx.user_id,
                AuthzTarget.for_product(ProductID(product_id)),
                Permission.READ_PRODUCT,
            )
        except InsufficientPermissionsError:
            await websocket.close(
                code=4403,
                reason="not authorized to observe product events",
            )
            return

    product_event_bus = await container.get(ProductEventBus)
    content_event_bus: ContentEventBus | None = None
    if has_note_content:
        content_event_bus = await container.get(ContentEventBus)

    product_id_obj = ProductID(product_id)
    streams: list[AsyncIterator[Event[Any]]] = [
        product_event_bus.subscribe(product_id_obj),
    ]
    if content_event_bus is not None:
        streams.append(content_event_bus.subscribe(product_id_obj))

    await websocket.accept()
    try:
        async for event in _fan_in(streams):
            await websocket.send_json(
                {
                    "kind": type(event.payload).KIND,
                    "product_id": str(event.product_id),
                    "actor_id": str(event.actor_id),
                    "payload": asdict(event.payload),
                    "occurred_at": event.occurred_at.isoformat(),
                },
            )
    except WebSocketDisconnect:
        pass


async def _fan_in(
    streams: list[AsyncIterator[Event[Any]]],
) -> AsyncIterator[Event[Any]]:
    """Merge several per-product event streams into one.

    Each input stream keeps its own publish ordering; the relative
    order across streams is whatever the underlying buses publish
    in. The SPA does not depend on cross-bus sequencing — every
    `kind` drives an independent slice of the React Query cache.

    Cancellation: when the consumer stops iterating (the WS
    disconnects or the handler exits), the generator's ``finally``
    cancels the pump tasks, which propagates ``CancelledError``
    into each subscribe iterator and runs its cleanup (unsubscribe
    from Redis, release the pubsub object).
    """
    # `None` is the per-stream completion marker — `Event` is a
    # dataclass and can never be `None`, so the discriminator is
    # unambiguous and lets mypy narrow the queue item to `Event[Any]`
    # after the sentinel and exception checks below.
    queue: asyncio.Queue[Event[Any] | BaseException | None] = asyncio.Queue()

    async def pump(stream: AsyncIterator[Event[Any]]) -> None:
        try:
            async for event in stream:
                await queue.put(event)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001
            await queue.put(exc)
        finally:
            await queue.put(None)

    tasks = [asyncio.create_task(pump(s)) for s in streams]
    pending = len(tasks)

    try:
        while pending > 0:
            item = await queue.get()
            if item is None:
                pending -= 1
                continue
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
