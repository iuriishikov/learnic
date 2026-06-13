from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.email.anon_rate_limit import (
    AnonymousEmailRateLimiter,
)
from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)


@dataclass(slots=True, frozen=True)
class RequestPasswordResetCommand:
    email: str


@final
class RequestPasswordResetCommandHandler:
    """Emit a reset email if the address is registered.

    Deliberately silent on unknown addresses so that attackers can't
    enumerate registered emails through the reset endpoint.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        email_tokens: EmailTokenStore,
        notifier: Notifier,
        config: SecurityPolicies,
        anon_rate_limiter: AnonymousEmailRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._email_tokens: Final = email_tokens
        self._notifier: Final = notifier
        self._config: Final = config
        self._anon_rate_limiter: Final = anon_rate_limiter

    async def run(self, data: RequestPasswordResetCommand) -> None:
        # Throttle by recipient regardless of whether the address is
        # registered — both blunts inbox-bombing and keeps the unknown
        # vs known timing identical (no enumeration via the limiter).
        await self._anon_rate_limiter.check(data.email)
        user = await self._user_gateway.with_email(data.email)
        if user is None:
            return

        raw_token = await self._email_tokens.issue(
            user.oid,
            EmailTokenPurpose.RESET,
            self._config.reset_password_token_ttl_seconds,
        )
        await self._transaction.commit()

        base = self._config.frontend_base_url.rstrip("/")
        link = f"{base}/reset-password?token={raw_token}"
        await self._notifier.send(
            recipient_id=user.oid,
            category=NotificationCategory.SECURITY,
            payloads={
                NotificationChannel.EMAIL: EmailPayload(
                    subject="Сброс пароля",
                    components=[
                        EmailParagraph.text("Здравствуйте!"),
                        EmailParagraph.text(
                            "Чтобы установить новый пароль, нажмите на кнопку ниже:",
                        ),
                        EmailButton(label="Сбросить пароль", url=link),
                        EmailParagraph.text("Ссылка действует 1 час."),
                    ],
                ),
            },
        )
