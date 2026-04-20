from collections.abc import AsyncIterator

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

from learnic.application.common.persistence.ping import PingReader
from learnic.application.queries.ping.ping import PingQueryHandler
from learnic.infrastructure.configs import (
    ASGIConfig,
    Configs,
    PostgresConfig,
)
from learnic.infrastructure.persistence.adapters.ping import PingReaderAlchemy


class ConfigsProvider(Provider):
    scope = Scope.APP

    configs = from_context(provides=Configs, scope=Scope.APP)

    @provide
    def postgres_config(self, configs: Configs) -> PostgresConfig:
        return configs.postgres

    @provide
    def asgi_config(self, configs: Configs) -> ASGIConfig:
        return configs.asgi


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

    ping_reader = provide(PingReaderAlchemy, provides=PingReader)


class InteractorsProvider(Provider):
    scope = Scope.REQUEST

    ping_handler = provide(PingQueryHandler)


def setup_providers(configs: Configs) -> AsyncContainer:
    return make_async_container(
        ConfigsProvider(),
        DBProvider(),
        GatewaysProvider(),
        InteractorsProvider(),
        context={Configs: configs},
    )
