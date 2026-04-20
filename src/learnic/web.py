from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from learnic.bootstrap import setup_map_tables, setup_routes
from learnic.infrastructure.configs import Configs
from learnic.ioc import setup_providers


def _create_app(configs: Configs) -> FastAPI:
    setup_map_tables()
    app = FastAPI()
    setup_routes(app)
    container = setup_providers(configs)
    setup_dishka(container, app)
    return app


def create_app_production(configs: Configs) -> FastAPI:
    return _create_app(configs)


def create_app_tests(configs: Configs) -> FastAPI:
    return _create_app(configs)
