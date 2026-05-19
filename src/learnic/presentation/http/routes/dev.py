"""Dev-only endpoints for local testing.

This router is registered in ``bootstrap.setup_routes`` **only when**
``AppConfig.environment == "development"``. In production the import
chain still runs (Python module load is harmless) but the router is
never attached to the FastAPI app — the routes physically do not
exist in prod, removing any risk of accidental activation by a
mis-set flag.

Currently exposes:

* ``POST /dev/jobs/reconcile-storage-quotas`` — manually enqueue the
  over-quota reconciliation pass. The same task fires daily on cron
  via the TaskIQ scheduler; this endpoint lets a developer trigger
  it without waiting for the next 03:00 UTC tick.
"""

from typing import Final

from dishka.integrations.fastapi import FromDishka
from fastapi import status
from fastapi_error_map import ErrorAwareRouter
from fastapi_error_map.rules import Rule

from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

dev_router = ErrorAwareRouter(
    prefix="/dev",
    tags=["Dev"],
    route_class=DishkaErrorAwareRoute,
)


_EMPTY_ERROR_MAP: Final[dict[type[Exception], int | Rule]] = {}


@dev_router.post(
    "/jobs/reconcile-storage-quotas",
    summary="Manually enqueue the storage-quota reconcile job",
    operation_id="devTriggerReconcileStorageQuotas",
    status_code=status.HTTP_202_ACCEPTED,
    error_map=_EMPTY_ERROR_MAP,
)
async def trigger_reconcile_storage_quotas(
    scheduler: FromDishka[TaskScheduler],
) -> None:
    """Enqueue one reconciliation pass via the task scheduler.

    Dev-only counterpart to the cron tick. The task itself walks
    every author with usage, opens / refreshes / resolves storage
    breaches, sends warnings and enforcement notifications. See
    :class:`ReconcileStorageQuotasCommandHandler` for the full
    flow.

    Args:
        scheduler: Injected task scheduler — its ``.kiq()`` call
            puts the task on the broker queue.

    Returns:
        ``202 Accepted`` once the task is on the queue. The actual
        run happens in the worker; check worker logs for the
        ``storage_quota_reconcile.done`` line with the summary
        counters.
    """
    await scheduler.schedule_reconcile_storage_quotas()
