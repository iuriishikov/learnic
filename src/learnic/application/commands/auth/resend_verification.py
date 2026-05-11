from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)


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
        notifier: Notifier,
        config: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._signup_sessions: Final = signup_sessions
        self._email_tokens: Final = email_tokens
        self._notifier: Final = notifier
        self._config: Final = config

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

        raw_token = await self._email_tokens.issue(
            user.oid,
            EmailTokenPurpose.VERIFY,
            self._config.verify_email_token_ttl_seconds,
        )
        await self._transaction.commit()
        base = self._config.frontend_base_url.rstrip("/")
        link = f"{base}/confirm/email?token={raw_token}"
        await self._notifier.send(
            recipient_id=user.oid,
            category=NotificationCategory.SECURITY,
            payloads={
                NotificationChannel.EMAIL: EmailPayload(
                    subject="Подтверждение email",
                    components=[
                        EmailParagraph.text("Здравствуйте!"),
                        EmailParagraph.text(
                            "Подтвердите ваш email, нажав на кнопку ниже:",
                        ),
                        EmailButton(label="Подтвердить email", url=link),
                        EmailParagraph.text("Ссылка действует 24 часа."),
                    ],
                ),
            },
        )
