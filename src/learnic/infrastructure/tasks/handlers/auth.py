"""TaskIQ handlers for auth-aggregate background work."""

import logging

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.auth.purge_unverified_users import (
    PurgeUnverifiedUsersCommand,
    PurgeUnverifiedUsersCommandHandler,
)
from learnic.infrastructure.tasks.broker import broker

_logger = logging.getLogger(__name__)


@broker.task(
    schedule=[{"cron": "0 3 * * *"}],
)
@inject
async def purge_unverified_users_task(
    handler: FromDishka[PurgeUnverifiedUsersCommandHandler],
) -> None:
    """Delete abandoned unverified accounts past self-recovery.

    Cron: ``0 3 * * *`` (every day at 03:00 UTC) via the TaskIQ
    scheduler (see ``learnic/worker.py``). Same nightly slot as the
    gift / collaboration-invite and storage-quota sweeps.

    A user who registered but never confirmed their email is locked
    out once their verify link (24h) and signup session (30m) expire:
    login is blocked, resend needs the gone session, and the UNIQUE
    ``email`` blocks re-registration, so the row squats that address
    forever. This sweep removes exactly those unrecoverable rows;
    ``email_tokens`` / ``signup_sessions`` children cascade via FK.

    Idempotent — a duplicate scheduler tick deletes zero rows on the
    second pass. The deleted count is logged for observability.
    """
    summary = await handler.run(PurgeUnverifiedUsersCommand())
    _logger.info(
        "unverified_users_purge.done",
        extra={"deleted": summary.deleted},
    )
