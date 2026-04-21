from typing import Protocol


class TaskScheduler(Protocol):
    """Enqueues background tasks from command handlers.

    Application handlers depend on this protocol to schedule work
    for later execution without knowing about the broker.
    Add one method per domain operation you need to enqueue.
    """

    async def schedule_example(self, payload: str) -> None: ...

    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        """Enqueue an ad-hoc HTML email for async delivery.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: Rendered HTML body.
            text: Optional plain-text alternative.
        """
        ...
