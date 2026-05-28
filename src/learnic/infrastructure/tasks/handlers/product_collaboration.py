"""TaskIQ handlers for product_collaboration-aggregate background work."""

import logging

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.product_collaboration.purge_expired_invites import (  # noqa: E501
    PurgeExpiredInvitesCommand,
    PurgeExpiredInvitesCommandHandler,
)
from learnic.infrastructure.tasks.broker import broker

_logger = logging.getLogger(__name__)


@broker.task(
    schedule=[{"cron": "0 3 * * *"}],
)
@inject
async def purge_expired_collaboration_invites_task(
    handler: FromDishka[PurgeExpiredInvitesCommandHandler],
) -> None:
    """Delete every PENDING_INVITE collaboration past its TTL.

    Cron: ``0 3 * * *`` (every day at 03:00 UTC) via the TaskIQ
    scheduler (see ``learnic/worker.py``). Same nightly slot as
    ``reconcile_storage_quotas_task`` — both are independent
    whole-population sweeps the worker pool drains in parallel.

    Acceptance only validates the ``invite_expires_at`` TTL at
    call time (see ``ProductCollaboration.accept`` /
    ``accept_in_app``) and never cleans up; without this sweep,
    expired pending rows accumulate forever and keep the partial
    unique index on ``(product_id, invited_email)`` for pending
    invites occupied. The cron does a single bulk ``DELETE``;
    grants cascade through the FK
    ``collaboration_grants.collaboration_id`` (``ON DELETE
    CASCADE``).

    Idempotent — a duplicate scheduler tick deletes zero rows on
    the second pass, so single-replica scheduling is not required
    for correctness. Delegates to the application handler with no
    payload; the deleted count is logged so the deploy can observe
    how busy the sweep is without hooking metrics in yet.
    """
    summary = await handler.run(PurgeExpiredInvitesCommand())
    _logger.info(
        "collaboration_invites_purge.done",
        extra={"deleted": summary.deleted},
    )
