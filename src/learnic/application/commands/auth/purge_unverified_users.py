"""Periodic purge of abandoned unverified user accounts.

A user who registered but never confirmed their email is stuck the
moment their verify-email link expires (1h) and their signup session
expires (30m): login is blocked (``EmailNotVerifiedError``), resend
needs the gone signup session, and re-registration is blocked by the
UNIQUE ``email`` — the row reserves that address forever. Without a
sweep these rows accumulate and squat real email addresses.

This sweep deletes exactly the rows that can no longer self-recover —
unverified, with no active VERIFY token and no active signup session.
The 1h verify-token TTL is the de-facto grace period: a user with a
live link (or who keeps hitting resend) is never touched. Wired to a
15-minute TaskIQ cron in ``infrastructure/tasks/handlers/auth.py``;
the same rows are also reclaimed on demand at re-registration. A
cluster-wide ``GlobalSchedulerLock`` single-flights the pass so an
overlapping or duplicate tick skips instead of stacking a second
full-table delete. Idempotent regardless — a duplicate pass deletes
zero rows.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.scheduler_lock import (
    GlobalSchedulerLock,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway

_logger = logging.getLogger(__name__)

# Cluster-wide key for the purge pass. Distinct from the storage-quota
# reconcile key, so the two periodic jobs never block each other (the
# advisory lock is keyed per hashed string).
_PURGE_LOCK_KEY: Final = "unverified_users_purge"


@dataclass(slots=True, frozen=True)
class PurgeUnverifiedUsersCommand:
    """No arguments — the sweep is whole-population."""


@dataclass(slots=True, frozen=True)
class PurgeUnverifiedUsersSummary:
    """Outcome of one purge pass (for structured logging)."""

    deleted: int


@final
class PurgeUnverifiedUsersCommandHandler:
    """Bulk-delete abandoned unverified accounts past self-recovery."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        scheduler_lock: GlobalSchedulerLock,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._scheduler_lock: Final = scheduler_lock

    async def run(
        self,
        data: PurgeUnverifiedUsersCommand,  # noqa: ARG002
    ) -> PurgeUnverifiedUsersSummary:
        if not await self._scheduler_lock.try_acquire(_PURGE_LOCK_KEY):
            _logger.info("unverified_users.purge_skipped_already_running")
            return PurgeUnverifiedUsersSummary(deleted=0)
        try:
            now = datetime.now(timezone.utc)
            deleted = await self._user_gateway.delete_abandoned_unverified(
                now,
            )
            await self._transaction.commit()
            _logger.info(
                "unverified_users.purged",
                extra={"deleted": deleted, "as_of": now.isoformat()},
            )
            return PurgeUnverifiedUsersSummary(deleted=deleted)
        finally:
            await self._scheduler_lock.release(_PURGE_LOCK_KEY)
