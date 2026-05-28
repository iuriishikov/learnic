from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CursorSnapshot:
    """One user's current cursor on a product, returned by ``snapshot``."""

    user_id: UserID
    field_id: str
    action: str | None
    updated_at: datetime


class CursorsState(Protocol):
    """Per-product map of which user is where right now.

    Keyed by ``(product_id, user_id)`` — one cursor per user. If a
    user opens two editor tabs, the latest ``publish_at`` wins; the
    other tab's view is whatever the server last broadcast. The
    ``conn_id`` token disambiguates disconnect cleanups so tab-1
    closing doesn't wipe tab-2's cursor.

    State is ephemeral. There is no persistence and no replay; on
    every connect, the SPA fetches a fresh snapshot via WS.
    """

    async def publish_at(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
        field_id: str,
        action: str | None,
        now: datetime,
    ) -> None:
        """Set / refresh the user's cursor at ``field_id``.

        ``now`` is stamped as ``last_seen`` and ``updated_at`` for
        the snapshot. ``conn_id`` is recorded so a later
        ``mark_disconnect`` can be a no-op if a fresher tab has
        taken over the user's cursor.
        """

    async def publish_leave(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
        field_id: str,
    ) -> bool:
        """Drop the user's cursor if it is on ``field_id``.

        Returns ``True`` if state was actually removed (caller
        should emit ``cursor_left`` on the bus). A stale ``conn_id``
        or a different ``field_id`` is a no-op and returns
        ``False`` — the user has already moved on.
        """

    async def mark_disconnect(
        self,
        product_id: ProductID,
        user_id: UserID,
        conn_id: str,
    ) -> bool:
        """Final cleanup when the user's WS closes.

        Returns ``True`` if state was actually removed (caller
        should emit ``user_gone`` on the bus). A no-op if another
        tab of the same user is still active (the stored
        ``conn_id`` doesn't match the disconnecting one).
        """

    async def snapshot(
        self,
        product_id: ProductID,
        *,
        exclude_user_id: UserID,
        now: datetime,
        stale_after_seconds: int,
    ) -> list[CursorSnapshot]:
        """Return current cursors for ``product_id``, minus self.

        Implementations prune entries whose ``last_seen`` is older
        than ``now - stale_after_seconds`` inline — the snapshot
        endpoint is the only place stale rows get cleaned up in
        the lazy model. The caller passes ``now`` so tests can
        freeze time.
        """
