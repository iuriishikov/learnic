from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.infrastructure.configs import SecurityConfig


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
        scheduler: TaskScheduler,
        config: SecurityConfig,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._email_tokens: Final = email_tokens
        self._scheduler: Final = scheduler
        self._config: Final = config

    async def run(self, data: RequestPasswordResetCommand) -> None:
        user = await self._user_gateway.with_email(data.email)
        if user is None:
            return

        raw_token = await self._email_tokens.issue(
            user.oid,
            EmailTokenPurpose.RESET,
            self._config.reset_password_token_ttl_seconds,
        )
        await self._transaction.commit()
        await self._scheduler.schedule_send_password_reset_email(
            user.email.value, raw_token
        )
