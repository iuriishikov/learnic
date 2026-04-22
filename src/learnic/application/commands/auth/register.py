from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EmailAlreadyRegisteredError
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
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    Patronymic,
    RawPassword,
)
from learnic.infrastructure.configs import SecurityConfig


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
        scheduler: TaskScheduler,
        config: SecurityConfig,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway
        self._hasher: Final = hasher
        self._email_tokens: Final = email_tokens
        self._signup_sessions: Final = signup_sessions
        self._scheduler: Final = scheduler
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

        await self._scheduler.schedule_send_verification_email(
            user.email.value, verify_token
        )
        return RegisterResult(
            user_id=user.oid,
            signup_session_token=signup_token,
        )
