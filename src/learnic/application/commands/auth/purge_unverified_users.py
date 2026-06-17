"""Periodic purge of abandoned unverified user accounts.

A user who registered but never confirmed their email is stuck the
moment their verify-email link expires (24h) and their signup session
expires (30m): login is blocked (``EmailNotVerifiedError``), resend
needs the gone signup session, and re-registration is blocked by the
UNIQUE ``email`` — the row reserves that address forever. Without a
sweep these rows accumulate and squat real email addresses.

This sweep deletes exactly the rows that can no longer self-recover —
unverified, with no active VERIFY token and no active signup session.
The 24h verify-token TTL is the de-facto grace period: a user with a
live link (or who keeps hitting resend) is never touched. Wired to a
daily TaskIQ cron in ``infrastructure/tasks/handlers/auth.py``.
Idempotent — a duplicate scheduler tick deletes zero rows on the
second pass.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway

_logger = logging.getLogger(__name__)


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
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(
        self,
        data: PurgeUnverifiedUsersCommand,  # noqa: ARG002
    ) -> PurgeUnverifiedUsersSummary:
        now = datetime.now(timezone.utc)
        deleted = await self._user_gateway.delete_abandoned_unverified(now)
        await self._transaction.commit()
        _logger.info(
            "unverified_users.purged",
            extra={"deleted": deleted, "as_of": now.isoformat()},
        )
        return PurgeUnverifiedUsersSummary(deleted=deleted)
