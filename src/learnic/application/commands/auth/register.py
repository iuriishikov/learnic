from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.email.anon_rate_limit import (
    AnonymousEmailRateLimiter,
)
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
from learnic.application.common.security.policies import SecurityPolicies
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


@dataclass(slots=True, frozen=True)
class RegisterCommand:
    email: str
    password: str
    first_name: str
    last_name: str
    patronymic: str | None = None
    distribution_consent: bool = False


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
        task_scheduler: TaskScheduler,
        config: SecurityPolicies,
        anon_rate_limiter: AnonymousEmailRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway
        self._hasher: Final = hasher
        self._email_tokens: Final = email_tokens
        self._signup_sessions: Final = signup_sessions
        self._task_scheduler: Final = task_scheduler
        self._config: Final = config
        self._anon_rate_limiter: Final = anon_rate_limiter

    async def run(self, data: RegisterCommand) -> RegisterResult:
        await self._anon_rate_limiter.check(data.email)
        if await self._user_gateway.with_email(data.email) is not None:
            # The address is taken. Reclaim it only if the holder is an
            # abandoned unverified registration past self-recovery (no
            # live verify token, no live signup session — exactly the
            # rows the periodic purge reaps): delete it on demand so the
            # new owner need not wait for the sweep. A verified account,
            # or one still inside its 1h verification window, is
            # untouchable and still rejects the registration. The delete
            # runs in this transaction, so the INSERT below reuses the
            # freed email without tripping the UNIQUE constraint.
            reclaimed = (
                await self._user_gateway.delete_abandoned_unverified_by_email(
                    data.email,
                    datetime.now(timezone.utc),
                )
            )
            if not reclaimed:
                raise EmailAlreadyRegisteredError

        user = User.create_user(
            email=Email(data.email),
            first_name=FirstName(data.first_name),
            last_name=LastName(data.last_name),
            patronymic=(
                Patronymic(data.patronymic) if data.patronymic is not None else None
            ),
            password_hash=await self._hasher.hash(RawPassword(data.password)),
            distribution_consent_at=(
                datetime.now(timezone.utc) if data.distribution_consent else None
            ),
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

        base = self._config.frontend_base_url.rstrip("/")
        link = f"{base}/confirm/email?token={verify_token}"
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
        return RegisterResult(
            user_id=user.oid,
            signup_session_token=signup_token,
        )
