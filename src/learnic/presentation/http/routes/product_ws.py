"""Product-level WebSocket channel.

Read-only push of :class:`ProductEvent` instances to the product
author. Mutations stay on the REST API — this socket fans out
post-commit deltas of product metadata (name / description /
duration / cover / status) and Q&A entries so two tabs of the same
author (or, later, a co-author) stay in sync without polling.

This channel is **separate** from the course-content channel
(``WS /courses/{course_id}/events``): course-content events
(modules / lessons / blocks / releases / draft reset) keep flowing
through `ContentEventBus`; everything in this channel comes from
`ProductEventBus`. Webinar defaults and cohorts are intentionally
**not** covered yet.

Protocol summary (kept here, not in OpenAPI — OpenAPI 3 doesn't
model WebSockets):

* **Auth.** Standard ``accessCookie`` HttpOnly cookie sent by the
  browser on the WS handshake. Failure closes with code ``4401``
  before ``accept``.
* **Authorization.** Only the product author can subscribe in
  Phase A; non-authors get ``4403``. When the
  ``ProductCollaborator`` feature lands, the check expands.
* **Lifecycle.** Server pushes events one-way until the client
  disconnects. No client→server messages are interpreted yet.
* **Initial state.** Client first calls ``GET /products/{id}``
  (and ``GET /products/{id}/qa`` if it cares about Q&A) over REST
  to load the product, then opens this socket to receive deltas.
  On reconnect, refetch + resubscribe — no event buffering /
  replay.

Server → client message shape::

    {
      "kind": "<ProductEventKind value>",
      "product_id": "<UUID>",
      "actor_id": "<UUID>",
      "payload": { ... },          # type-specific fields
      "occurred_at": "<ISO 8601>",
    }
"""

from typing import Final
from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.product_events.event_bus import (
    ProductEventBus,
)
from learnic.entities.product.ids import ProductID
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
    """One-way push of :class:`ProductEvent` for a single product.

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
        if product.author_id != ctx.user_id:
            await websocket.close(code=4403, reason="not the product author")
            return

    event_bus = await container.get(ProductEventBus)

    await websocket.accept()
    try:
        async for event in event_bus.subscribe(ProductID(product_id)):
            await websocket.send_json(
                {
                    "kind": event.kind.value,
                    "product_id": str(event.product_id),
                    "actor_id": str(event.actor_id),
                    "payload": event.payload,
                    "occurred_at": event.occurred_at.isoformat(),
                },
            )
    except WebSocketDisconnect:
        pass
