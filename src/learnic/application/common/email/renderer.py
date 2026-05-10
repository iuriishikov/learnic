from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from learnic.application.common.email.components import EmailComponent


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """Rendered HTML body and plain-text alternative for one email."""

    html: str
    text: str


class EmailRenderer(Protocol):
    """Render typed email components into HTML + a plain-text alternative.

    Application code (command handlers, the notification publisher)
    composes a :class:`Sequence[EmailComponent]` and calls
    :meth:`render` to get the finished payload, which is then handed
    to :meth:`TaskScheduler.schedule_send_email`. The infrastructure
    adapter owns the templating engine, the brand layout, and any
    asset URLs — application stays component-only.
    """

    def render(
        self,
        recipient: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> RenderedEmail:
        """Render ``components`` into a branded HTML body and text body.

        Args:
            recipient: Recipient email address — passed through to the
                base layout (e.g. for "Sent to {recipient}" footer).
            subject: Email subject line — also exposed to the layout
                template for ``<title>`` etc.
            components: Ordered body of the email.

        Returns:
            Rendered HTML and plain-text bodies, ready to be enqueued
            via :meth:`TaskScheduler.schedule_send_email`.
        """
        ...
