from enum import StrEnum


class PresenceStatus(StrEnum):
    """Whether a user has at least one live session.

    Derived state, not persisted: computed from connection records in
    Redis. ``ONLINE`` means at least one connection's heartbeat is fresh
    within ``PRESENCE_TTL_SECONDS``; ``OFFLINE`` otherwise.
    """

    ONLINE = "online"
    OFFLINE = "offline"
