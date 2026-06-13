from collections.abc import Sequence
from typing import Protocol

from learnic.entities.push_subscription.models import PushSubscription
from learnic.entities.user.models import UserID


class PushSubscriptionGateway(Protocol):
    """Write-side persistence for :class:`PushSubscription` rows.

    Browsers re-issue subscriptions whenever the push service
    rotates the endpoint, so :meth:`upsert` is the primary write
    path: same endpoint string → existing row, refresh keys and
    ``last_seen_at``; new endpoint → fresh row. The unique
    constraint on ``endpoint`` makes upserting safe.
    """

    async def upsert(self, subscription: PushSubscription) -> None: ...

    async def delete_by_endpoint(
        self,
        endpoint: str,
        user_id: UserID,
    ) -> bool:
        """Delete the caller's subscription with the given endpoint.

        Scoped to ``user_id`` so one user can never delete another
        user's subscription by presenting its (opaque but possibly
        leaked) endpoint string. Returns ``True`` if a row was
        removed, ``False`` if the endpoint was absent for that user.
        Callers can ignore the return — unsubscribe is idempotent at
        the HTTP boundary.
        """
        ...

    async def list_for_user(
        self,
        user_id: UserID,
    ) -> Sequence[PushSubscription]:
        """Return every subscription owned by ``user_id``.

        Used both by the settings UI (devices list) and by the
        push-fanout worker; ordering is by ``created_at`` ascending
        so the worker hits the oldest device first — irrelevant for
        correctness but makes failure logs easier to read.
        """
        ...
