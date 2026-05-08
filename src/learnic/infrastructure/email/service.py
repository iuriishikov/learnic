from collections.abc import Sequence
from typing import Final

from typing_extensions import override

from learnic.application.common.email.components import EmailComponent
from learnic.application.common.email.sender import EmailSender
from learnic.application.common.email.service import EmailService
from learnic.infrastructure.email.renderer import EmailRenderer


class TemplatedEmailService(EmailService):
    """Renders typed components and dispatches via :class:`EmailSender`.

    The component list goes through :class:`EmailRenderer` (Jinja-based,
    branded base layout); the resulting HTML and plain-text alternative
    are then handed to the underlying transport.
    """

    def __init__(
        self,
        renderer: EmailRenderer,
        sender: EmailSender,
    ) -> None:
        self._renderer: Final = renderer
        self._sender: Final = sender

    @override
    async def send(
        self,
        to: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> None:
        html = self._renderer.render_html(to, subject, components)
        text = self._renderer.render_text(components)
        await self._sender.send(to=to, subject=subject, html=html, text=text)
