from typing_extensions import override

from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.infrastructure.tasks.handlers.example import example_task


class TaskSchedulerTaskIQ(TaskScheduler):
    @override
    async def schedule_example(self, payload: str) -> None:
        await example_task.kiq(payload)
