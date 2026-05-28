"""Periodic purge of expired ``PENDING_INVITE`` collaboration rows.

Acceptance only validates ``invite_expires_at > now`` at call time
and never cleans up — see ``ProductCollaboration.accept`` /
``accept_in_app``. Without a sweep, expired pending rows accumulate
forever and keep the partial unique index on
``(product_id, invited_email)`` for pending invites occupied, which
forces a manual ``revoke`` before the same address can be invited
again.

The handler is wired to a daily TaskIQ cron in
``infrastructure/tasks/handlers/product_collaboration.py``. One
``DELETE`` per pass; grants follow via FK ``ON DELETE CASCADE``.
Idempotent — a duplicate scheduler tick deletes zero rows on the
second pass, so single-replica scheduling is not required.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PurgeExpiredInvitesCommand:
    """No arguments — the sweep is whole-population.

    Kept as a dataclass for shape-consistency with every other
    handler's command DTO so the dishka wiring and unit-test
    harness do not need a special case.
    """


@dataclass(slots=True, frozen=True)
class PurgeExpiredInvitesSummary:
    """Outcome of one purge pass.

    Surfaced to the caller (TaskIQ handler) for structured
    logging — there is no business consumer.
    """

    deleted: int


@final
class PurgeExpiredInvitesCommandHandler:
    """Bulk-delete every PENDING_INVITE collaboration past its TTL."""

    def __init__(
        self,
        transaction: Transaction,
        collaboration_gateway: ProductCollaborationGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._collaboration_gateway: Final = collaboration_gateway

    async def run(
        self,
        data: PurgeExpiredInvitesCommand,  # noqa: ARG002
    ) -> PurgeExpiredInvitesSummary:
        now = datetime.now(timezone.utc)
        deleted = (
            await self._collaboration_gateway.delete_expired_pending_invites(
                expires_before=now,
            )
        )
        await self._transaction.commit()
        _logger.info(
            "collaboration_invites.purged",
            extra={"deleted": deleted, "expires_before": now.isoformat()},
        )
        return PurgeExpiredInvitesSummary(deleted=deleted)
