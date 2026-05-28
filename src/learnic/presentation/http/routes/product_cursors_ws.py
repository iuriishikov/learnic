"""Live editor-cursor channel for one product.

Bidirectional WebSocket carrying per-user "I am at field X doing
Y" deltas between every editor / viewer of a product. The server
keeps no semantic knowledge of fields — ``field_id`` and ``action``
are opaque strings whose taxonomy lives in the SPA. The server
only relays, snapshots, and cleans up on disconnect.

See the ``## WebSocket channels`` section of ``info.description``
(rendered in ``web.py``) for the full protocol.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.cursors.constants import (
    ACTION_MAX_LEN,
    CURSOR_STALE_SECONDS,
    FIELD_ID_MAX_LEN,
)
from learnic.application.common.cursors.event_bus import CursorsEventBus
from learnic.application.common.cursors.events import (
    CursorsEvent,
    CursorsEventKind,
)
from learnic.application.common.cursors.state import CursorsState
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    InvalidTokenError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/products")


_PRODUCT_ID_PATH: Final = Path(
    description="Target product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _envelope_at(event: CursorsEvent) -> dict[str, str | None]:
    return {
        "type": CursorsEventKind.CURSOR_AT.value,
        "user_id": str(event.user_id),
        "field_id": event.field_id,
        "action": event.action,
        "updated_at": event.occurred_at.isoformat(),
    }


def _envelope_left(event: CursorsEvent) -> dict[str, str | None]:
    return {
        "type": CursorsEventKind.CURSOR_LEFT.value,
        "user_id": str(event.user_id),
        "field_id": event.field_id,
    }


def _envelope_gone(event: CursorsEvent) -> dict[str, str | None]:
    return {
        "type": CursorsEventKind.USER_GONE.value,
        "user_id": str(event.user_id),
    }


def _envelope_from_event(event: CursorsEvent) -> dict[str, str | None] | None:
    """Translate an in-process bus event to its outgoing WS shape."""
    if event.kind is CursorsEventKind.CURSOR_AT:
        return _envelope_at(event)
    if event.kind is CursorsEventKind.CURSOR_LEFT:
        return _envelope_left(event)
    if event.kind is CursorsEventKind.USER_GONE:
        return _envelope_gone(event)
    return None


def _normalize_field_id(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    if not trimmed or len(trimmed) > FIELD_ID_MAX_LEN:
        return None
    return trimmed


def _normalize_action(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    if len(trimmed) > ACTION_MAX_LEN:
        return None
    return trimmed


@router.websocket("/{product_id}/cursors")
async def product_cursors_ws(
    websocket: WebSocket,
    product_id: UUID = _PRODUCT_ID_PATH,
) -> None:
    """Bidirectional cursor stream for one product.

    See the ``## WebSocket channels`` section in the API
    description for the full protocol (auth, close codes,
    lifecycle, message shapes).
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    # Short-lived request scope — DB session used by the auth /
    # authz check is released before the long-lived WS lifetime.
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
                Permission.READ_PRODUCT,
            )
        except InsufficientPermissionsError:
            await websocket.close(
                code=4403,
                reason="not authorized to observe product cursors",
            )
            return

    state = await container.get(CursorsState)
    event_bus = await container.get(CursorsEventBus)

    product_id_obj = ProductID(product_id)
    conn_id = str(uuid.uuid4())

    await websocket.accept()

    # Initial snapshot — current state of every other user's cursor.
    initial = await state.snapshot(
        product_id_obj,
        exclude_user_id=ctx.user_id,
        now=_now(),
        stale_after_seconds=CURSOR_STALE_SECONDS,
    )
    await websocket.send_json(
        {
            "type": "snapshot",
            "cursors": [
                {
                    "user_id": str(item.user_id),
                    "field_id": item.field_id,
                    "action": item.action,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in initial
            ],
        },
    )

    async def receive_loop() -> None:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            field_id = _normalize_field_id(msg.get("field_id"))
            if field_id is None:
                continue
            if kind == CursorsEventKind.CURSOR_AT.value:
                action = _normalize_action(msg.get("action"))
                now = _now()
                await state.publish_at(
                    product_id_obj,
                    ctx.user_id,
                    conn_id,
                    field_id,
                    action,
                    now,
                )
                await event_bus.publish(
                    CursorsEvent(
                        kind=CursorsEventKind.CURSOR_AT,
                        product_id=product_id_obj,
                        user_id=ctx.user_id,
                        field_id=field_id,
                        action=action,
                        occurred_at=now,
                    ),
                )
            elif kind == CursorsEventKind.CURSOR_LEFT.value:
                removed = await state.publish_leave(
                    product_id_obj,
                    ctx.user_id,
                    conn_id,
                    field_id,
                )
                if not removed:
                    continue
                await event_bus.publish(
                    CursorsEvent(
                        kind=CursorsEventKind.CURSOR_LEFT,
                        product_id=product_id_obj,
                        user_id=ctx.user_id,
                        field_id=field_id,
                        action=None,
                        occurred_at=_now(),
                    ),
                )

    async def forward_loop() -> None:
        async for event in event_bus.subscribe(product_id_obj):
            # Skip self echo — the originator already updated its
            # local store before publishing.
            if event.user_id == ctx.user_id:
                continue
            envelope = _envelope_from_event(event)
            if envelope is None:
                continue
            await websocket.send_json(envelope)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(receive_loop())
            tg.create_task(forward_loop())
    except* WebSocketDisconnect:
        pass
    finally:
        removed = await state.mark_disconnect(
            product_id_obj,
            ctx.user_id,
            conn_id,
        )
        if removed:
            await event_bus.publish(
                CursorsEvent(
                    kind=CursorsEventKind.USER_GONE,
                    product_id=product_id_obj,
                    user_id=ctx.user_id,
                    field_id=None,
                    action=None,
                    occurred_at=_now(),
                ),
            )
