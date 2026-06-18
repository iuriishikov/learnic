from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.email.anon_rate_limit import (
    AnonymousEmailRateLimiter,
)
from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.constants import (
    VERIFY_EMAIL_TOKEN_TTL_SECONDS,
)
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.application.common.tasks.scheduler import TaskScheduler


@dataclass(slots=True, frozen=True)
class ResendVerificationCommand:
    signup_session_token: str


@final
class ResendVerificationCommandHandler:
    """Re-issue a verification email for the registration tab.

    Identifies the pending user via the ``signup_session`` cookie
    issued on ``POST /auth/register``. Issuing a new token implicitly
    invalidates any previously-active VERIFY token for the user (see
    :meth:`EmailTokenStore.issue`), so older links stop working —
    this is exactly what resend should do.

    Silently no-ops when the user is already verified (the email is
    cosmetic at that point and we don't want to leak verification
    state through error shape).
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        signup_sessions: SignupSessionStore,
        email_tokens: EmailTokenStore,
        task_scheduler: TaskScheduler,
        config: SecurityPolicies,
        anon_rate_limiter: AnonymousEmailRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._signup_sessions: Final = signup_sessions
        self._email_tokens: Final = email_tokens
        self._task_scheduler: Final = task_scheduler
        self._config: Final = config
        self._anon_rate_limiter: Final = anon_rate_limiter

    async def run(self, data: ResendVerificationCommand) -> None:
        user_id = await self._signup_sessions.resolve(
            data.signup_session_token,
        )
        if user_id is None:
            raise InvalidTokenError

        user = await self._user_gateway.with_id(user_id)
        if user is None:
            raise InvalidTokenError
        if user.email_verified:
            return

        await self._anon_rate_limiter.check(user.email.value)
        raw_token = await self._email_tokens.issue(
            user.oid,
            EmailTokenPurpose.VERIFY,
            VERIFY_EMAIL_TOKEN_TTL_SECONDS,
        )
        await self._transaction.commit()
        base = self._config.frontend_base_url.rstrip("/")
        link = f"{base}/confirm/email?token={raw_token}"
        await self._task_scheduler.schedule_send_email(
            to=user.email.value,
            subject="Подтверждение email",
            components=[
                EmailParagraph.text("Здравствуйте!"),
                EmailParagraph.text(
                    "Подтвердите ваш email, нажав на кнопку ниже:",
                ),
                EmailButton(label="Подтвердить email", url=link),
                EmailParagraph.text("Ссылка действует 1 час."),
            ],
        )
