from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.common.email.sender import EmailSender
from learnic.infrastructure.tasks.broker import broker


@broker.task
@inject(patch_module=True)
async def send_email_task(
    to: str,
    subject: str,
    html: str,
    text: str | None,
    sender: FromDishka[EmailSender],
) -> None:
    """Deliver an ad-hoc HTML email via the configured provider.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html: Rendered HTML body.
        text: Optional plain-text alternative.
        sender: Injected email transport.
    """
    await sender.send(to=to, subject=subject, html=html, text=text)
