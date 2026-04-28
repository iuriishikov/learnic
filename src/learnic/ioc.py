from collections.abc import AsyncIterator

import aioboto3
import httpx
from dishka import (
    AsyncContainer,
    Provider,
    Scope,
    from_context,
    make_async_container,
    provide,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from types_aiobotocore_s3 import S3Client

from learnic.application.commands.auth.login import LoginCommandHandler
from learnic.application.commands.auth.logout import LogoutCommandHandler
from learnic.application.commands.auth.logout_all import (
    LogoutAllCommandHandler,
)
from learnic.application.commands.auth.refresh import RefreshCommandHandler
from learnic.application.commands.auth.register import (
    RegisterCommandHandler,
)
from learnic.application.commands.auth.request_password_reset import (
    RequestPasswordResetCommandHandler,
)
from learnic.application.commands.auth.reset_password import (
    ResetPasswordCommandHandler,
)
from learnic.application.commands.auth.verify_email import (
    VerifyEmailCommandHandler,
)
from learnic.application.commands.auth.verify_wait import (
    VerifyWaitCommandHandler,
)
from learnic.application.commands.user.avatar.remove import (
    RemoveUserAvatarCommandHandler,
)
from learnic.application.commands.user.avatar.set import (
    SetUserAvatarCommandHandler,
)
from learnic.application.commands.user.change_description import (
    ChangeUserDescriptionCommandHandler,
)
from learnic.application.commands.user.change_first_name import (
    ChangeUserFirstNameCommandHandler,
)
from learnic.application.commands.user.change_last_name import (
    ChangeUserLastNameCommandHandler,
)
from learnic.application.commands.user.change_patronymic import (
    ChangeUserPatronymicCommandHandler,
)
from learnic.application.commands.user.cover.remove import (
    RemoveUserCoverCommandHandler,
)
from learnic.application.commands.user.cover.set import (
    SetUserCoverCommandHandler,
)
from learnic.application.common.email.sender import EmailSender
from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
)
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.email_tokens import EmailTokenStore
from learnic.application.common.security.html import HtmlSanitizer
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.queries.user.get import GetUserQueryHandler
from learnic.application.queries.user.get_avatar import (
    GetUserAvatarQueryHandler,
)
from learnic.application.queries.user.get_cover import (
    GetUserCoverQueryHandler,
)
from learnic.infrastructure.configs import (
    ASGIConfig,
    Configs,
    PostgresConfig,
    RusenderConfig,
    S3Config,
    SecurityConfig,
    TaskIQConfig,
)
from learnic.infrastructure.email.adapters.rusender import (
    RusenderEmailSender,
)
from learnic.infrastructure.persistence.adapters.email_token import (
    EmailTokenStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.file import (
    FilesMapperAlchemy,
    FilesReaderAlchemy,
)
from learnic.infrastructure.persistence.adapters.refresh_token import (
    RefreshTokenStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.signup_session import (
    SignupSessionStoreAlchemy,
)
from learnic.infrastructure.persistence.adapters.token_denylist import (
    TokenDenylistAlchemy,
)
from learnic.infrastructure.persistence.adapters.transaction import (
    EntitySaverAlchemy,
    TransactionAlchemy,
)
from learnic.infrastructure.persistence.adapters.user import (
    UserMapperAlchemy,
    UserReaderAlchemy,
)
from learnic.infrastructure.security.argon2_hasher import (
    Argon2PasswordHasher,
)
from learnic.infrastructure.security.bleach_html_sanitizer import (
    BleachHtmlSanitizer,
)
from learnic.infrastructure.security.jwt_access import JwtAccessTokenService
from learnic.infrastructure.storage.adapters.s3 import S3FileStorage
from learnic.infrastructure.tasks.scheduler import TaskSchedulerTaskIQ
from learnic.presentation.http.common.auth_deps import Authenticator


class ConfigsProvider(Provider):
    scope = Scope.APP

    configs = from_context(provides=Configs, scope=Scope.APP)

    @provide
    def postgres_config(self, configs: Configs) -> PostgresConfig:
        return configs.postgres

    @provide
    def asgi_config(self, configs: Configs) -> ASGIConfig:
        return configs.asgi

    @provide
    def s3_config(self, configs: Configs) -> S3Config:
        return configs.s3

    @provide
    def taskiq_config(self, configs: Configs) -> TaskIQConfig:
        return configs.taskiq

    @provide
    def rusender_config(self, configs: Configs) -> RusenderConfig:
        return configs.rusender

    @provide
    def security_config(self, configs: Configs) -> SecurityConfig:
        return configs.security


class DBProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(
        self,
        postgres: PostgresConfig,
    ) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(postgres.dsn_async, echo=postgres.debug)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide
    def session_maker(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        maker: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session


class GatewaysProvider(Provider):
    scope = Scope.REQUEST

    transaction = provide(TransactionAlchemy, provides=Transaction)
    entity_saver = provide(EntitySaverAlchemy, provides=EntitySaver)
    user_gateway = provide(UserMapperAlchemy, provides=UserGateway)
    user_reader = provide(UserReaderAlchemy, provides=UserReader)
    files_gateway = provide(FilesMapperAlchemy, provides=FilesGateway)
    files_reader = provide(FilesReaderAlchemy, provides=FilesReader)


class SecurityProvider(Provider):
    hasher = provide(Argon2PasswordHasher, provides=PasswordHasher, scope=Scope.APP)
    access_tokens = provide(
        JwtAccessTokenService,
        provides=AccessTokenService,
        scope=Scope.APP,
    )
    refresh_store = provide(
        RefreshTokenStoreAlchemy,
        provides=RefreshTokenStore,
        scope=Scope.REQUEST,
    )
    email_tokens = provide(
        EmailTokenStoreAlchemy,
        provides=EmailTokenStore,
        scope=Scope.REQUEST,
    )
    signup_sessions = provide(
        SignupSessionStoreAlchemy,
        provides=SignupSessionStore,
        scope=Scope.REQUEST,
    )
    denylist = provide(
        TokenDenylistAlchemy,
        provides=TokenDenylist,
        scope=Scope.REQUEST,
    )
    html_sanitizer = provide(
        BleachHtmlSanitizer,
        provides=HtmlSanitizer,
        scope=Scope.APP,
    )
    authenticator = provide(Authenticator, scope=Scope.REQUEST)


class S3Provider(Provider):
    scope = Scope.APP

    @provide
    def session(self) -> aioboto3.Session:
        return aioboto3.Session()

    @provide
    async def client(
        self,
        session: aioboto3.Session,
        s3: S3Config,
    ) -> AsyncIterator[S3Client]:
        async with session.client(
            "s3",
            endpoint_url=s3.endpoint,
            aws_access_key_id=s3.access_key,
            aws_secret_access_key=s3.secret_key,
            region_name=s3.region,
        ) as client:
            yield client

    @provide(scope=Scope.REQUEST)
    def file_storage(
        self,
        client: S3Client,
    ) -> FileStorage:
        return S3FileStorage(client)


class TasksProvider(Provider):
    scope = Scope.REQUEST

    scheduler = provide(TaskSchedulerTaskIQ, provides=TaskScheduler)


class InteractorsProvider(Provider):
    scope = Scope.REQUEST

    get_user = provide(GetUserQueryHandler)
    get_user_avatar = provide(GetUserAvatarQueryHandler)
    get_user_cover = provide(GetUserCoverQueryHandler)

    register = provide(RegisterCommandHandler)
    login = provide(LoginCommandHandler)
    refresh = provide(RefreshCommandHandler)
    logout = provide(LogoutCommandHandler)
    logout_all = provide(LogoutAllCommandHandler)
    verify_email = provide(VerifyEmailCommandHandler)
    verify_wait = provide(VerifyWaitCommandHandler)
    request_password_reset = provide(RequestPasswordResetCommandHandler)
    reset_password = provide(ResetPasswordCommandHandler)

    set_user_avatar = provide(SetUserAvatarCommandHandler)
    remove_user_avatar = provide(RemoveUserAvatarCommandHandler)
    set_user_cover = provide(SetUserCoverCommandHandler)
    remove_user_cover = provide(RemoveUserCoverCommandHandler)

    change_user_first_name = provide(ChangeUserFirstNameCommandHandler)
    change_user_last_name = provide(ChangeUserLastNameCommandHandler)
    change_user_patronymic = provide(ChangeUserPatronymicCommandHandler)
    change_user_description = provide(ChangeUserDescriptionCommandHandler)


class EmailProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        client = httpx.AsyncClient(timeout=10.0)
        try:
            yield client
        finally:
            await client.aclose()

    @provide(scope=Scope.REQUEST)
    def email_sender(
        self,
        client: httpx.AsyncClient,
        rusender: RusenderConfig,
    ) -> EmailSender:
        return RusenderEmailSender(
            client=client,
            api_key=rusender.api_key,
            from_email=rusender.from_email,
            from_name=rusender.from_name,
        )


def setup_providers(configs: Configs) -> AsyncContainer:
    return make_async_container(
        ConfigsProvider(),
        DBProvider(),
        GatewaysProvider(),
        SecurityProvider(),
        S3Provider(),
        TasksProvider(),
        EmailProvider(),
        InteractorsProvider(),
        context={Configs: configs},
    )
