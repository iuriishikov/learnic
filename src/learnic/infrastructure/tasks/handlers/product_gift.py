"""TaskIQ handlers for product_gift-aggregate background work."""

import logging

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.product_gift.purge_expired_invites import (
    PurgeExpiredGiftsCommand,
    PurgeExpiredGiftsCommandHandler,
)
from learnic.infrastructure.tasks.broker import broker

_logger = logging.getLogger(__name__)


@broker.task(
    schedule=[{"cron": "0 3 * * *"}],
)
@inject
async def purge_expired_gifts_task(
    handler: FromDishka[PurgeExpiredGiftsCommandHandler],
) -> None:
    """Delete every PENDING_INVITE gift past its TTL.

    Cron: ``0 3 * * *`` (every day at 03:00 UTC) via the TaskIQ
    scheduler (see ``learnic/worker.py``). Same nightly slot as the
    collaboration-invite and storage-quota sweeps.

    Acceptance only validates the ``invite_expires_at`` TTL at call
    time (see ``ProductGift.accept`` / ``accept_in_app``) and never
    cleans up; without this sweep, expired pending rows accumulate
    and keep the partial unique index on
    ``(product_id, invited_email)`` for pending gifts occupied.

    Idempotent — a duplicate scheduler tick deletes zero rows on the
    second pass. The deleted count is logged for observability.
    """
    summary = await handler.run(PurgeExpiredGiftsCommand())
    _logger.info(
        "product_gifts_purge.done",
        extra={"deleted": summary.deleted},
    )
