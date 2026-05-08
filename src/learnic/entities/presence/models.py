from dataclasses import dataclass
from datetime import datetime

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


@dataclass
class Presence(BaseEntity[UserID]):
    """Read-only snapshot of a user's presence at a point in time.

    Identified by ``UserID`` (one record per user). Not persisted in
    Postgres — derived from Redis connection records. Constructed by
    readers/handlers, never mutated through the entity itself.
    """

    status: PresenceStatus
    last_seen_at: datetime
