from collections.abc import Sequence
from typing import Protocol

from learnic.application.common.email.components import EmailComponent
from learnic.entities.user.models import UserID


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
        components: Sequence[EmailComponent],
    ) -> None:
        """Enqueue an email built from typed body components.

        Every transactional email — verification, password reset,
        collaboration flows, in-app notification fanout — goes through
        this single method. Callers describe the body as a list of
        :class:`EmailComponent` instances; the scheduler implementation
        renders them into HTML + plain-text alternative before handing
        the result to :class:`EmailSender` via the worker.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            components: Ordered body of the email — typed components
                rendered into the branded base layout.
        """
        ...

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
        """Enqueue a Web Push fanout to every subscription of ``user_id``.

        Args:
            user_id: Recipient user.
            title: System banner title.
            body: System banner body text.
            url: Optional click target opened by the SW.
            tag: Optional notification tag for in-place replacement.
            icon: Optional icon URL.
            category: :class:`NotificationCategory` value used for
                preference enforcement at the worker; ``None`` skips
                the check (system / ops broadcasts).
            bypass_preferences: ``True`` for the manual "Send test"
                path — the worker delivers regardless of the
                per-category opt-in.
        """
        ...
