from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.errors import EmailAlreadyRegisteredError
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    Patronymic,
    RawPassword,
)
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.models import Wallet


@dataclass(slots=True, frozen=True)
class RegisterCommand:
    email: str
    password: str
    first_name: str
    last_name: str
    patronymic: str | None = None


@dataclass(slots=True, frozen=True)
class RegisterResult:
    user_id: UserID
    signup_session_token: str


@final
class RegisterCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        user_gateway: UserGateway,
        hasher: PasswordHasher,
        email_tokens: EmailTokenStore,
        signup_sessions: SignupSessionStore,
        notifier: Notifier,
        config: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway
        self._hasher: Final = hasher
        self._email_tokens: Final = email_tokens
        self._signup_sessions: Final = signup_sessions
        self._notifier: Final = notifier
        self._config: Final = config

    async def run(self, data: RegisterCommand) -> RegisterResult:
        if await self._user_gateway.with_email(data.email) is not None:
            raise EmailAlreadyRegisteredError

        user = User.create_user(
            email=Email(data.email),
            first_name=FirstName(data.first_name),
            last_name=LastName(data.last_name),
            patronymic=(
                Patronymic(data.patronymic) if data.patronymic is not None else None
            ),
            password_hash=self._hasher.hash(RawPassword(data.password)),
        )
        self._entity_saver.add_one(user)
        # Flush so the users row exists for the FK-referencing INSERTs below.
        await self._transaction.flush()

        # Every new user gets a RUB wallet at registration. Multi-currency
        # wallets will be added lazily when the platform launches markets
        # beyond RU; until then a single RUB wallet is enough.
        self._entity_saver.add_one(
            Wallet.create_for_user(
                user_id=user.oid,
                currency=Currency.RUB,
            ),
        )

        verify_token = await self._email_tokens.issue(
            user.oid,
            EmailTokenPurpose.VERIFY,
            self._config.verify_email_token_ttl_seconds,
        )
        signup_token = await self._signup_sessions.issue(
            user.oid,
            self._config.signup_session_ttl_seconds,
        )
        await self._transaction.commit()

        base = self._config.frontend_base_url.rstrip("/")
        link = f"{base}/confirm/email?token={verify_token}"
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
        return RegisterResult(
            user_id=user.oid,
            signup_session_token=signup_token,
        )
