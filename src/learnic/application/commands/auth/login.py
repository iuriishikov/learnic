import logging
from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.auth.common import TokenPair
from learnic.application.common.errors import (
    AccountBannedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.refresh_tokens import (
    DeviceContext,
    RefreshTokenStore,
)
from learnic.entities.notification.models import Notification
from learnic.entities.user.value_objects import RawPassword

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class LoginCommand:
    email: str
    password: str
    device: DeviceContext | None = None


@final
class LoginCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        hasher: PasswordHasher,
        access_tokens: AccessTokenService,
        refresh_store: RefreshTokenStore,
        notification_publisher: NotificationPublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._hasher: Final = hasher
        self._access_tokens: Final = access_tokens
        self._refresh_store: Final = refresh_store
        self._notification_publisher: Final = notification_publisher

    async def run(self, data: LoginCommand) -> TokenPair:
        user = await self._user_gateway.with_email(data.email)
        if user is None:
            raise InvalidCredentialsError
        if not self._hasher.verify(RawPassword(data.password), user.password_hash):
            raise InvalidCredentialsError
        if user.is_banned:
            raise AccountBannedError(user.oid)
        if not user.email_verified:
            raise EmailNotVerifiedError

        refresh = await self._refresh_store.issue(user.oid, device=data.device)
        access = self._access_tokens.issue(user.oid, refresh.record.family_id)
        await self._transaction.commit()

        try:
            notification = Notification.for_new_login(
                recipient_id=user.oid,
                session_id=refresh.record.family_id,
                device_label=data.device.device_label if data.device else None,
                user_agent=data.device.user_agent if data.device else None,
                ip_address=data.device.ip_address if data.device else None,
            )
            await self._notification_publisher.publish(notification)
        except Exception:
            _logger.exception(
                "Failed to publish new_login notification for user %s",
                user.oid,
            )

        return TokenPair(
            access_token=access.token,
            access_expires_at=access.payload.expires_at,
            refresh_token=refresh.token,
            refresh_expires_at=refresh.record.expires_at,
        )
