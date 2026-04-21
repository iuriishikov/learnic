from typing import Any, Final

import httpx
from typing_extensions import override

from learnic.application.common.email.sender import (
    EmailSender,
    EmailSendError,
)

_API_BASE: Final = "https://api.rusender.ru/api/v1"
_SEND_PATH: Final = "/external-mails/send"


class RusenderEmailSender(EmailSender):
    """Rusender HTTP adapter implementing :class:`EmailSender`.

    Uses a shared :class:`httpx.AsyncClient` for connection pooling.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        from_email: str,
        from_name: str = "",
    ) -> None:
        self._client: Final = client
        self._api_key: Final = api_key
        self._from_email: Final = from_email
        self._from_name: Final = from_name

    @override
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        mail: dict[str, Any] = {
            "to": {"email": to},
            "from": self._from_block(),
            "subject": subject,
            "html": html,
        }
        if text is not None:
            mail["text"] = text
        await self._post(_SEND_PATH, {"mail": mail})

    def _from_block(self) -> dict[str, str]:
        block = {"email": self._from_email}
        if self._from_name:
            block["name"] = self._from_name
        return block

    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        response = await self._client.post(
            f"{_API_BASE}{path}",
            json=payload,
            headers={"X-Api-Key": self._api_key},
        )
        if response.is_error:
            raise EmailSendError(
                f"Rusender {response.status_code}: {response.text}",
            )
