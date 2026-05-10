"""Per-user confirm-events WebSocket channel.

One-way push of :class:`ConfirmEvent` deltas to initiator tabs that
are waiting on a single-token email confirmation. Used by the
registration page (`/verify-email`) to react in real time when the
user clicks the verification link on another device, and by future
profile pages that wait on email-confirmed actions (change-email,
delete-account, ...).

Authentication accepts EITHER the access cookie OR the signup
session cookie — the channel is meaningful both for already-logged-in
users (e.g. profile flows) and for the registration tab that doesn't
hold an access cookie yet.

The full protocol — close codes, replay policy, kind list — lives in
``## WebSocket channels`` of the OpenAPI ``info.description``.
"""

from typing import Any

from dishka import AsyncContainer
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from learnic.application.common.auth.confirm_events import (
    ConfirmEvent,
    ConfirmEventBus,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import Authenticator
from learnic.presentation.http.common.cookies import (
    ACCESS_COOKIE,
    SIGNUP_SESSION_COOKIE,
)

router = APIRouter(prefix="/users/me")


def _envelope(event: ConfirmEvent) -> dict[str, Any]:
    return {"kind": event.kind.value, "purpose": event.purpose}


async def _resolve_user_id(
    websocket: WebSocket,
    container: AsyncContainer,
) -> UserID | None:
    """Resolve the channel key from either auth cookie.

    Tries the access cookie first (logged-in users), falls back to
    the signup-session cookie (registration tab). Returns ``None`` if
    neither yields a live identity.
    """
    if websocket.cookies.get(ACCESS_COOKIE):
        async with container() as request_scope:
            auth = await request_scope.get(Authenticator)
            try:
                ctx = await auth.authenticate_websocket(websocket)
            except InvalidTokenError:
                pass
            else:
                return ctx.user_id

    raw_signup = websocket.cookies.get(SIGNUP_SESSION_COOKIE)
    if raw_signup:
        async with container() as request_scope:
            signup_sessions: SignupSessionStore = await request_scope.get(
                SignupSessionStore,
            )
            user_id: UserID | None = await signup_sessions.resolve(raw_signup)
            if user_id is not None:
                return user_id

    return None


@router.websocket("/confirm-events")
async def confirm_events_ws(websocket: WebSocket) -> None:
    """One-way push of email-confirmation events to the initiator.

    The recipient is derived from cookies — there is no path
    parameter, so a tab can subscribe to exactly its own channel.
    Authentication failures close with ``4401`` before ``accept``.

    Replay policy: none. If the connection drops between issue and
    confirm, the client should reconnect AND refetch state via REST
    (e.g. ``GET /auth/email-verification/wait`` for signup) to avoid
    missing the transition.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    user_id = await _resolve_user_id(websocket, container)
    if user_id is None:
        await websocket.close(code=4401, reason="invalid token")
        return

    event_bus = await container.get(ConfirmEventBus)

    await websocket.accept()
    try:
        async for event in event_bus.subscribe(user_id):
            await websocket.send_json(_envelope(event))
    except WebSocketDisconnect:
        pass
