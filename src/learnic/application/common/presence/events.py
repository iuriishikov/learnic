from dataclasses import dataclass
from datetime import datetime

from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class PresenceEvent:
    """Status-change notification published on the presence event bus.

    Emitted by ``PresenceTracker`` only on real edge transitions —
    ``OFFLINE → ONLINE`` (first connection) and ``ONLINE → OFFLINE``
    (last connection closed). Heartbeats and additional connections of
    an already-online user do not produce events.
    """

    user_id: UserID
    status: PresenceStatus
    occurred_at: datetime
