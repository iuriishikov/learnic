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

    async def schedule_send_verification_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        """Enqueue delivery of an email-verification link.

        Args:
            to: Recipient email address.
            raw_token: Single-use token; the worker builds the verify
                URL from the configured frontend base URL.
        """
        ...

    async def schedule_send_password_reset_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        """Enqueue delivery of a password-reset link.

        Args:
            to: Recipient email address.
            raw_token: Single-use token; the worker builds the reset URL
                from the configured frontend base URL.
        """
        ...
