from collections.abc import Sequence
from typing import Protocol

from learnic.application.common.email.components import EmailComponent


class EmailService(Protocol):
    """High-level email transport that renders typed components.

    Handlers and tasks depend on this Protocol instead of building HTML
    strings or talking to :class:`EmailSender` directly. The adapter
    renders the component list into a branded HTML body (with a plain
    text alternative) and forwards it to the underlying transport.
    """

    async def send(
        self,
        to: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> None:
        """Render ``components`` and dispatch the message to ``to``.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            components: Ordered body of the email; rendered into the
                shared base layout with header, signature, and footer.

        Raises:
            EmailSendError: The underlying transport refused or failed
                to deliver the message.
        """
        ...
