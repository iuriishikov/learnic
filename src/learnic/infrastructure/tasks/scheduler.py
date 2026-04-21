from typing_extensions import override

from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.infrastructure.tasks.handlers.email import send_email_task
from learnic.infrastructure.tasks.handlers.example import example_task


class TaskSchedulerTaskIQ(TaskScheduler):
    @override
    async def schedule_example(self, payload: str) -> None:
        await example_task.kiq(payload)

    @override
    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        # @inject strips `sender` at runtime, but .kiq type stubs
        # still expect it; silencing is the documented workaround.
        await send_email_task.kiq(to, subject, html, text)  # type: ignore[call-overload]
