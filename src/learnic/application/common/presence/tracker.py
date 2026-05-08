from typing import Protocol

from learnic.entities.user.models import UserID


class PresenceTracker(Protocol):
    """Tracks live user sessions and answers online-status queries.

    A "session" is a single client connection (e.g. one WebSocket).
    Multiple concurrent sessions per user are expected — a user is
    ``ONLINE`` while at least one of their sessions is live and has
    refreshed its heartbeat within the configured TTL.

    Implementations are responsible for publishing
    ``PresenceEvent`` on edge transitions (first connection in /
    last connection out) via the injected event bus.
    """

    async def mark_online(self, user_id: UserID, conn_id: str) -> None:
        """Register a new live session ``conn_id`` for ``user_id``."""

    async def mark_offline(self, user_id: UserID, conn_id: str) -> None:
        """Drop a session ``conn_id``. No-op if it was never registered."""

    async def heartbeat(self, user_id: UserID, conn_id: str) -> None:
        """Refresh the freshness timestamp of an existing session."""

    async def is_online(self, user_id: UserID) -> bool:
        """Return ``True`` if at least one session of ``user_id`` is fresh."""

    async def filter_online(
        self,
        user_ids: list[UserID],
    ) -> set[UserID]:
        """Return the subset of ``user_ids`` currently online.

        Intended for batch lookups (e.g. building a presence snapshot
        for a roster). Implementations should pipeline the underlying
        store calls.
        """
