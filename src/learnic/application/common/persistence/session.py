import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SessionView:
    """Read-side projection of an active refresh-token family ("session").

    Every row in ``refresh_tokens`` is denormalised with the device
    metadata captured at issue/rotation time. A "session" groups a
    family (one per device/login) and is built from the family's
    active row plus aggregates over the family's full history:

    - ``family_id`` doubles as the public session id used by
      ``DELETE /auth/sessions/{family_id}``.
    - ``created_at`` is ``MIN(issued_at)`` over the family — when the
      device first logged in.
    - ``last_used_at`` is the active row's ``issued_at`` — when this
      session was last refreshed.
    - ``expires_at`` is the active row's ``expires_at`` — when the
      cookie naturally dies if no refresh occurs first.
    - ``ip_address``/``user_agent``/``device_label`` are the active
      row's denormalised metadata, i.e. the latest seen values.
    """

    family_id: uuid.UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None
    device_label: str | None


class SessionsReader(Protocol):
    """Read-side queries for the user's active refresh-token sessions."""

    async def list_for_user(self, user_id: UserID) -> list[SessionView]:
        """Return every active (non-revoked, non-expired) session.

        Ordered by ``last_used_at`` descending — the device the user
        is most likely sitting at right now comes first.
        """
        ...
