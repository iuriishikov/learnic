from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from learnic.bootstrap import setup_configs, setup_map_tables, setup_routes
from learnic.infrastructure.configs import Configs
from learnic.infrastructure.tasks.broker import broker
from learnic.ioc import setup_providers


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    await broker.startup()
    try:
        yield
    finally:
        await broker.shutdown()


def _create_app(configs: Configs) -> FastAPI:
    setup_map_tables()
    app = FastAPI(lifespan=_lifespan)
    setup_routes(app)
    container = setup_providers(configs)
    setup_dishka(container, app)
    return app


def create_app_production() -> FastAPI:
    return _create_app(setup_configs())


def create_app_tests(configs: Configs) -> FastAPI:
    return _create_app(configs)
