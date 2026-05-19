"""TaskIQ handlers for billing-aggregate background work."""

import logging

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.billing.reconcile_storage_quotas import (
    ReconcileStorageQuotasCommand,
    ReconcileStorageQuotasCommandHandler,
)
from learnic.infrastructure.tasks.broker import broker

_logger = logging.getLogger(__name__)


@broker.task(
    schedule=[{"cron": "0 3 * * *"}],
)
@inject
async def reconcile_storage_quotas_task(
    handler: FromDishka[ReconcileStorageQuotasCommandHandler],
) -> None:
    """Run one over-quota reconciliation pass.

    Cron: ``0 3 * * *`` (every day at 03:00 UTC) via the TaskIQ
    scheduler (see ``learnic/worker.py``). The cadence is a daily
    sweep — fine for breach detection and warning, fine for the
    14-day grace cleanup. Manual triggers (dev endpoint or ad-hoc
    ``.kiq()``) go through the same task, the schedule label is
    additive.

    Delegates to the application handler with no payload — the scan
    is whole-population. The summary is logged so the deploy can
    observe how many users were scanned / warned / enforced per
    pass without hooking metrics in yet.
    """
    summary = await handler.run(ReconcileStorageQuotasCommand())
    _logger.info(
        "storage_quota_reconcile.done",
        extra={
            "scanned": summary.scanned,
            "breaches_opened": summary.breaches_opened,
            "breaches_refreshed": summary.breaches_refreshed,
            "breaches_resolved": summary.breaches_resolved,
            "enforcements": summary.enforcements,
            "warnings_sent": summary.warnings_sent,
        },
    )
