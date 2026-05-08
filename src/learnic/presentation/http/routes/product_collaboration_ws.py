"""Product-collaboration WebSocket channel.

One-way push of :class:`CollaborationEvent` deltas — invite,
accept, revoke, grants-updated — to clients with the right to
manage collaborators on a product. The contract is documented
in `## WebSocket channels` of the OpenAPI ``info.description``;
this module is the routing wire-up.

Subscribers must hold ``MANAGE_COLLABORATORS`` (or be the product
author — short-circuited by :class:`Authorizer`). Anyone else
gets ``4403`` and the socket is closed before ``accept``.
"""

from typing import Final
from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    InvalidTokenError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.product_collaboration_events.event_bus import (
    CollaborationEventBus,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/products")


_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


@router.websocket("/{product_id}/collaboration-events")
async def collaboration_ws(
    websocket: WebSocket,
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """One-way push of :class:`CollaborationEvent` for a single product.

    See ``## WebSocket channels`` in the OpenAPI description for the
    full protocol — close codes, envelope shape, and the exhaustive
    ``kind`` value list.
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

        authorizer = await request_scope.get(Authorizer)
        try:
            await authorizer.require(
                ctx.user_id,
                AuthzTarget.for_product(ProductID(product_id)),
                Permission.MANAGE_COLLABORATORS,
            )
        except InsufficientPermissionsError:
            await websocket.close(
                code=4403,
                reason="not authorized to observe collaboration events",
            )
            return

    event_bus = await container.get(CollaborationEventBus)

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
