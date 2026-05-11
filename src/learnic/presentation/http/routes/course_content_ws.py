"""Collaborative course-content WebSocket channel.

Read-only push of :class:`ContentEvent` instances to authors
connected to the same product. Mutations stay on the REST API —
this socket is purely a fan-out for post-commit deltas, so two
authors editing the same course see each other's changes
without polling.

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
  disconnects. No client→server messages are interpreted yet
  (they will land for presence / cursors in a later phase).
* **Initial state.** Client first calls
  ``GET /products/{id}/content/draft`` (REST) to load the tree,
  then opens this socket to receive deltas. On reconnect, refetch
  + resubscribe — no event buffering / replay.

Server → client message shape::

    {
      "kind": "<ContentEventKind value>",
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
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/courses")


_COURSE_ID_PATH: Final = Path(
    description="Target course product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


@router.websocket("/{course_id}/events")
async def course_content_ws(
    websocket: WebSocket,
    course_id: UUID = _COURSE_ID_PATH,
) -> None:
    """One-way push of :class:`ContentEvent` for a single course.

    See module-level docstring for the full protocol.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    # Short-lived REQUEST scope so the DB session used by token
    # denylist + product lookup is released as soon as auth +
    # ownership are verified.
    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return

        product_gateway = await request_scope.get(ProductGateway)
        product = await product_gateway.with_id(ProductID(course_id))
        if product is None or not product.supports(
            ProductCapability.HAS_COURSE_CONTENT,
        ):
            await websocket.close(code=4404, reason="course not found")
            return

        authorizer = await request_scope.get(Authorizer)
        try:
            await authorizer.require(
                ctx.user_id,
                AuthzTarget.for_product(ProductID(course_id)),
                Permission.READ_PRODUCT,
            )
        except InsufficientPermissionsError:
            await websocket.close(
                code=4403,
                reason="not authorized to observe course content events",
            )
            return

    event_bus = await container.get(ContentEventBus)

    await websocket.accept()
    try:
        async for event in event_bus.subscribe(ProductID(course_id)):
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
