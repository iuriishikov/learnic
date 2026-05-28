"""Periodic purge of expired ``PENDING_INVITE`` gift rows.

Acceptance only validates ``invite_expires_at > now`` at call time
and never cleans up — see ``ProductGift.accept`` / ``accept_in_app``.
Without a sweep, expired pending rows accumulate and keep the partial
unique index on ``(product_id, invited_email)`` for pending gifts
occupied. Wired to a daily TaskIQ cron in
``infrastructure/tasks/handlers/product_gift.py``. Idempotent — a
duplicate scheduler tick deletes zero rows on the second pass.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
)
from learnic.application.common.persistence.transaction import Transaction

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PurgeExpiredGiftsCommand:
    """No arguments — the sweep is whole-population."""


@dataclass(slots=True, frozen=True)
class PurgeExpiredGiftsSummary:
    """Outcome of one purge pass (for structured logging)."""

    deleted: int


@final
class PurgeExpiredGiftsCommandHandler:
    """Bulk-delete every PENDING_INVITE gift past its TTL."""

    def __init__(
        self,
        transaction: Transaction,
        gift_gateway: ProductGiftGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gift_gateway: Final = gift_gateway

    async def run(
        self,
        data: PurgeExpiredGiftsCommand,  # noqa: ARG002
    ) -> PurgeExpiredGiftsSummary:
        now = datetime.now(timezone.utc)
        deleted = await self._gift_gateway.delete_expired_pending_invites(
            expires_before=now,
        )
        await self._transaction.commit()
        _logger.info(
            "product_gifts.purged",
            extra={"deleted": deleted, "expires_before": now.isoformat()},
        )
        return PurgeExpiredGiftsSummary(deleted=deleted)
