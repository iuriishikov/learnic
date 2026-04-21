from typing import Protocol


class EmailSendError(Exception):
    """Raised when the email provider refused or failed to send a message."""


class EmailSender(Protocol):
    """Outbound email transport.

    Handlers depend on this Protocol to dispatch transactional emails
    without knowing the provider (Rusender, SES, SMTP, etc.).
    """

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        """Send an ad-hoc HTML email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: Rendered HTML body.
            text: Optional plain-text alternative; improves deliverability.

        Raises:
            EmailSendError: Provider rejected the request or returned a
                non-success response.
        """
        ...
