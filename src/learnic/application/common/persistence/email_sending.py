from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


class EmailSendingGateway(Protocol):
    """Write-side support for the per-user email-send rate limit.

    Backs :class:`EmailSendRateLimiter`. The two methods are used
    together inside one transaction: ``acquire_actor_lock`` serialises
    concurrent sends for the same actor so the count-then-insert
    sequence cannot race, and ``count_since`` reads how many emails the
    actor has already triggered in the window. The insert itself goes
    through the shared ``EntitySaver`` — this gateway never writes or
    commits.
    """

    async def acquire_actor_lock(self, actor_id: UserID) -> None:
        """Take a transaction-scoped advisory lock keyed on ``actor_id``.

        Concurrent calls for the same actor block here until the
        holding transaction commits or rolls back; different actors
        never contend. Released automatically on transaction end —
        callers do not unlock by hand. Acquiring the lock *before*
        :meth:`count_since` is what makes the rate-limit check
        race-free: two simultaneous sends can no longer both read the
        same count and both slip past the cap.
        """
        ...

    async def count_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        """Count emails ``actor_id`` has triggered at or after ``since``."""
        ...
