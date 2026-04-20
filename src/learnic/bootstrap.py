from fastapi import FastAPI

from learnic.infrastructure.configs import Configs, load_configs
from learnic.presentation.http.v1.routes.ping import router as ping_router


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI) -> None:
    app.include_router(ping_router, prefix="/api/v1")


def setup_map_tables() -> None:
    pass
