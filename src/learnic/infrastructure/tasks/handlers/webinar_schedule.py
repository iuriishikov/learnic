from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.commands.webinar_schedule.materialize import (
    DEFAULT_MATERIALIZE_LIMIT,
    MaterializeWebinarScheduleCommand,
    MaterializeWebinarScheduleCommandHandler,
)
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.infrastructure.tasks.broker import broker


@broker.task
@inject(patch_module=True)
async def materialize_webinar_schedule_task(
    schedule_id: WebinarScheduleID,
    handler: FromDishka[MaterializeWebinarScheduleCommandHandler],
) -> None:
    """Run :class:`MaterializeWebinarScheduleCommandHandler` in the worker.

    Thin TaskIQ wrapper — the heavy lifting (loading the schedule,
    computing the cursor, expanding the rrule, writing sessions)
    lives in the application command handler so the same path is
    testable via Mock-based unit tests.
    """
    await handler.run(
        MaterializeWebinarScheduleCommand(
            schedule_id=schedule_id,
            limit=DEFAULT_MATERIALIZE_LIMIT,
        ),
    )
