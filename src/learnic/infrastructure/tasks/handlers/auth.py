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
    schedule=[{"cron": "*/15 * * * *"}],
)
@inject
async def purge_unverified_users_task(
    handler: FromDishka[PurgeUnverifiedUsersCommandHandler],
) -> None:
    """Delete abandoned unverified accounts past self-recovery.

    Cron: ``*/15 * * * *`` (every 15 minutes) via the TaskIQ
    scheduler (see ``learnic/worker.py``). The frequent cadence frees
    a squatted address within ~15 min of it becoming reclaimable
    instead of up to a day; re-registration also reclaims the exact
    same rows on demand (see ``RegisterCommandHandler``), so this is
    the backstop sweep, not the only path.

    A user who registered but never confirmed their email is locked
    out once their verify link (24h) and signup session (30m) expire:
    login is blocked, resend needs the gone session, and the UNIQUE
    ``email`` blocks re-registration, so the row squats that address
    forever. This sweep removes exactly those unrecoverable rows;
    ``email_tokens`` / ``signup_sessions`` children cascade via FK.

    The handler holds a cluster-wide ``GlobalSchedulerLock`` for the
    pass, so a tick that overlaps a still-running pass (the 15-min
    interval is shorter than a worst-case full-table sweep) or a
    duplicate from an accidentally-scaled scheduler skips instead of
    stacking a second delete. Idempotent regardless — a duplicate
    tick deletes zero rows. The deleted count is logged.
    """
    summary = await handler.run(PurgeUnverifiedUsersCommand())
    _logger.info(
        "unverified_users_purge.done",
        extra={"deleted": summary.deleted},
    )
