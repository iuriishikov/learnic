from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)


@dataclass(slots=True, frozen=True)
class VerifyTokenCommand:
    token: str


@dataclass(slots=True, frozen=True)
class VerifyTokenResult:
    """Outcome of consuming an email-confirmation token.

    ``purpose`` echoes :class:`EmailTokenPurpose` so the SPA can pick
    the right success copy / redirect for an unknown-but-routable
    purpose without per-purpose frontend code.
    """

    purpose: str


# Purposes routed through the unified dispatcher. Adding a new
# email-confirmation flow means appending its purpose here AND adding
# the corresponding ``case`` arm in :meth:`VerifyTokenCommandHandler.run`
# along with a constructor dependency on its specialized handler.
#
# Purposes intentionally NOT routed here:
# - ``RESET`` — confirm step requires a new password in the body, so
#   the SPA submits to ``POST /auth/password-reset/confirm`` directly.
_UNIFIED_PURPOSES: Final[frozenset[EmailTokenPurpose]] = frozenset(
    {EmailTokenPurpose.VERIFY},
)


@final
class VerifyTokenCommandHandler:
    """Consume any single-token email confirmation in one endpoint.

    Looks up the token's purpose without consuming, then delegates to
    the specialized command handler that knows how to apply the
    confirmation. Specialized handlers retain their own routes for
    typed SDK calls; this dispatcher is what the unified
    ``/confirm/<purpose>`` SPA page hits so new purposes don't require
    a frontend deploy.
    """

    def __init__(
        self,
        email_tokens: EmailTokenStore,
        verify_email: VerifyEmailCommandHandler,
    ) -> None:
        self._email_tokens: Final = email_tokens
        self._verify_email: Final = verify_email

    async def run(self, data: VerifyTokenCommand) -> VerifyTokenResult:
        info = await self._email_tokens.peek(data.token)
        if info.purpose not in _UNIFIED_PURPOSES:
            # Purpose exists in the system but is not routable through
            # this endpoint (e.g. RESET, which needs a body field).
            # From the caller's perspective the token is not
            # consumable here — same shape as expired/unknown.
            raise InvalidTokenError

        match info.purpose:
            case EmailTokenPurpose.VERIFY:
                await self._verify_email.run(
                    VerifyEmailCommand(token=data.token),
                )
            case _:  # pragma: no cover - guarded by _UNIFIED_PURPOSES
                raise InvalidTokenError

        return VerifyTokenResult(purpose=info.purpose.value)
