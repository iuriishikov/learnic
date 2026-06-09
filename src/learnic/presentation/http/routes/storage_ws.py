"""Per-user live storage-quota WebSocket channel.

One-way push of the caller's quota pool — plan code, byte cap,
used and remaining bytes. A full ``snapshot`` envelope is sent
immediately after the handshake (no REST bootstrap needed), then
a ``usage_changed`` envelope follows every committed mutation of
the pool. Same shape and authentication as the notifications
channel; the contract is documented in ``## WebSocket channels``
of the OpenAPI ``info.description``.
"""

from datetime import datetime, timezone
from typing import Any

from dishka import AsyncContainer
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
    StorageQuotaEventKind,
    StorageQuotaUsageEvent,
    usage_event_from_snapshot,
)
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/users/me")


def _envelope(event: StorageQuotaUsageEvent) -> dict[str, Any]:
    return {
        "kind": event.kind.value,
        "plan_code": str(event.plan_code),
        "storage_bytes_max": event.storage_bytes_max,
        "storage_bytes_used": event.storage_bytes_used,
        "storage_bytes_remaining": event.storage_bytes_remaining,
        "occurred_at": event.occurred_at.isoformat(),
    }


@router.websocket("/storage")
async def storage_ws(websocket: WebSocket) -> None:
    """One-way push of the caller's storage-quota pool.

    The quota owner is derived from the access cookie — there is
    no path parameter, so a user subscribes to exactly their own
    pool and nothing else (a collaborator watching the author's
    pool uses ``GET /notes/{note_id}/storage-remaining`` instead).
    Authentication failures close with ``4401`` before ``accept``.

    The initial ``snapshot`` is computed inside a short-lived
    request scope so the DB session is released before the
    long-lived subscribe loop starts — same discipline as the
    handshake auth.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return
        entitlement = await request_scope.get(EntitlementService)
        snapshot = await entitlement.snapshot_for(ctx.user_id)

    event_bus = await container.get(StorageQuotaEventBus)

    await websocket.accept()
    try:
        await websocket.send_json(
            _envelope(
                usage_event_from_snapshot(
                    snapshot,
                    occurred_at=datetime.now(timezone.utc),
                    kind=StorageQuotaEventKind.SNAPSHOT,
                ),
            ),
        )
        async for event in event_bus.subscribe(ctx.user_id):
            await websocket.send_json(_envelope(event))
    except WebSocketDisconnect:
        pass
