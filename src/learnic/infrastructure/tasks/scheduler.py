from collections.abc import Sequence
from typing import Final

from typing_extensions import override

from learnic.application.common.email.components import EmailComponent
from learnic.application.common.email.renderer import EmailRenderer
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID
from learnic.infrastructure.tasks.handlers.billing import (
    reconcile_storage_quotas_task,
)
from learnic.infrastructure.tasks.handlers.email import send_email_task
from learnic.infrastructure.tasks.handlers.example import example_task
from learnic.infrastructure.tasks.handlers.file import (
    purge_file_from_storage_task,
)
from learnic.infrastructure.tasks.handlers.web_push import send_web_push_task


class TaskSchedulerTaskIQ(TaskScheduler):
    """TaskIQ-backed :class:`TaskScheduler`.

    For email the scheduler owns the render step: callers describe the
    body as :class:`EmailComponent` values, the scheduler turns them
    into HTML + plain-text via :class:`EmailRenderer` and only the
    finished payload crosses the broker. That keeps every command
    handler free of the renderer dependency and ensures the wire
    representation is plain strings — no shape-fragile dataclass
    serialisation through Redis.
    """

    def __init__(self, renderer: EmailRenderer) -> None:
        self._renderer: Final = renderer

    @override
    async def schedule_example(self, payload: str) -> None:
        await example_task.kiq(payload)

    @override
    async def schedule_purge_file_from_storage(
        self,
        file_id: FileID,
        attempt: int = 0,
    ) -> None:
        # @inject strips `handler` at runtime; .kiq stubs still see it.
        await purge_file_from_storage_task.kiq(  # type: ignore[call-overload]
            file_id,
            attempt,
        )

    @override
    async def schedule_reconcile_storage_quotas(self) -> None:
        # @inject strips `handler` at runtime; .kiq stubs still see it.
        await reconcile_storage_quotas_task.kiq()  # type: ignore[call-overload]

    @override
    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> None:
        rendered = self._renderer.render(
            recipient=to,
            subject=subject,
            components=components,
        )
        # @inject strips `sender` at runtime, but .kiq type stubs
        # still expect it; silencing is the documented workaround.
        await send_email_task.kiq(  # type: ignore[call-overload]
            to,
            subject,
            rendered.html,
            rendered.text,
        )

    @override
    async def schedule_send_web_push(
        self,
        *,
        user_id: UserID,
        title: str,
        body: str,
        url: str | None = None,
        tag: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        bypass_preferences: bool = False,
    ) -> None:
        await send_web_push_task.kiq(  # type: ignore[call-overload]
            user_id,
            title,
            body,
            url,
            tag,
            icon,
            category,
            bypass_preferences,
        )
