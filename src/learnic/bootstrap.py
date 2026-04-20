from fastapi import FastAPI

from learnic.infrastructure.configs import Configs, load_configs
from learnic.presentation.http.routes.root import router as root_router


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI) -> None:
    app.include_router(root_router)


def setup_map_tables() -> None:
    pass
