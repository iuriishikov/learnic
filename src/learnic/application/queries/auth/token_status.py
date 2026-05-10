from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.security.email_tokens import EmailTokenStore


@dataclass(slots=True, frozen=True)
class GetTokenStatusQuery:
    token: str


@dataclass(slots=True, frozen=True)
class TokenStatusView:
    """Public view of an email-confirmation token's status.

    Returned to the SPA so it can decide what to render before
    consuming. ``purpose`` mirrors :class:`EmailTokenPurpose` values.
    """

    purpose: str


@final
class GetTokenStatusQueryHandler:
    """Validate an email-confirmation token without consuming it.

    Used by the SPA to:
    - render a form-based confirm screen (e.g. ``/reset-password``)
      only when the link is still live;
    - look up ``purpose`` so a generic ``/confirm/<purpose>`` page can
      pick localized copy before consuming.

    Raises :class:`InvalidTokenError` (HTTP 401) if the token is
    unknown, already consumed, or expired.
    """

    def __init__(self, email_tokens: EmailTokenStore) -> None:
        self._email_tokens: Final = email_tokens

    async def run(self, data: GetTokenStatusQuery) -> TokenStatusView:
        info = await self._email_tokens.peek(data.token)
        return TokenStatusView(purpose=info.purpose.value)
