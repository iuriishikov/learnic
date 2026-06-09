"""Per-note live storage-panel WebSocket channel.

One-way push of the editor's storage card data — this note's own
byte usage plus the author's pool (cap / used / remaining). A full
``snapshot`` envelope is sent immediately after the handshake (no
REST bootstrap needed), then a ``usage_changed`` envelope follows
every committed mutation of the AUTHOR'S pool — uploads into
sibling notes move ``storage_bytes_remaining`` too, so the channel
listens to the whole pool, not just this note. The contract lives
in ``## WebSocket channels`` of the OpenAPI ``info.description``.

Internally this subscribes to the same per-owner
:class:`StorageQuotaEventBus` channel as ``WS /users/me/storage``
and re-reads the note's own usage on every event in a short-lived
request scope — pool numbers ride on the event itself.
"""

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from dishka import AsyncContainer
from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    InvalidTokenError,
)
from learnic.application.common.persistence.billing import FileUsageReader
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
    StorageQuotaEventKind,
    StorageQuotaUsageEvent,
    usage_event_from_snapshot,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/notes")

_NOTE_ID_PATH: Final = Path(
    description="Target note product's UUID.",
    examples=["3f2c8e64-7b3a-4d2c-9d11-9d4f0a44b6c8"],
)


def _envelope(
    event: StorageQuotaUsageEvent,
    note_used: int,
) -> dict[str, Any]:
    return {
        "kind": event.kind.value,
        "plan_code": str(event.plan_code),
        "note_storage_bytes_used": note_used,
        "storage_bytes_max": event.storage_bytes_max,
        "storage_bytes_used": event.storage_bytes_used,
        "storage_bytes_remaining": event.storage_bytes_remaining,
        "occurred_at": event.occurred_at.isoformat(),
    }


@router.websocket("/{note_id}/storage")
async def note_storage_ws(
    websocket: WebSocket,
    note_id: UUID = _NOTE_ID_PATH,
) -> None:
    """One-way push of this note's storage usage + the author's pool.

    Auth and authorization mirror ``GET /notes/{note_id}/storage``:
    access cookie (``4401``), note must exist (``4404``), actor
    must hold ``EDIT_LESSONS`` (``4403``) — all checked before
    ``accept``. Quota is anchored on the note author, so the
    collaborators and the author watching the same note all see
    identical numbers.
    """
    container: AsyncContainer = websocket.app.state.dishka_container
    note_id_obj = ProductID(note_id)

    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return

        product_gateway = await request_scope.get(ProductGateway)
        product = await product_gateway.with_id(note_id_obj)
        if product is None:
            await websocket.close(code=4404, reason="note not found")
            return

        authorizer = await request_scope.get(Authorizer)
        try:
            await authorizer.require(
                ctx.user_id,
                AuthzTarget.for_product(note_id_obj),
                Permission.EDIT_LESSONS,
            )
        except InsufficientPermissionsError:
            await websocket.close(
                code=4403,
                reason="not authorized to observe note storage",
            )
            return

        author_id = product.author_id
        entitlement = await request_scope.get(EntitlementService)
        snapshot = await entitlement.snapshot_for(author_id)
        file_usage = await request_scope.get(FileUsageReader)
        note_used = await file_usage.bytes_used_by_product(note_id_obj)

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
                note_used,
            ),
        )
        async for event in event_bus.subscribe(author_id):
            # Pool numbers ride on the event; the note's own share is
            # re-read per event in a fresh request scope so the DB
            # session never outlives one message.
            async with container() as event_scope:
                file_usage = await event_scope.get(FileUsageReader)
                note_used = await file_usage.bytes_used_by_product(
                    note_id_obj,
                )
            await websocket.send_json(_envelope(event, note_used))
    except WebSocketDisconnect:
        pass
