from collections.abc import AsyncIterator

import aioboto3
from aiobotocore.client import AioBaseClient
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

from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.infrastructure.configs import (
    ASGIConfig,
    Configs,
    PostgresConfig,
    S3Config,
    TaskIQConfig,
)
from learnic.infrastructure.persistence.adapters.transaction import (
    EntitySaverAlchemy,
    TransactionAlchemy,
)
from learnic.infrastructure.storage.adapters.s3 import S3FileStorage
from learnic.infrastructure.tasks.scheduler import TaskSchedulerTaskIQ


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
    ) -> AsyncIterator[AioBaseClient]:
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
        client: AioBaseClient,
        s3: S3Config,
    ) -> FileStorage:
        return S3FileStorage(client, s3.bucket)


class TasksProvider(Provider):
    scope = Scope.REQUEST

    scheduler = provide(TaskSchedulerTaskIQ, provides=TaskScheduler)


def setup_providers(configs: Configs) -> AsyncContainer:
    return make_async_container(
        ConfigsProvider(),
        DBProvider(),
        GatewaysProvider(),
        S3Provider(),
        TasksProvider(),
        context={Configs: configs},
    )
