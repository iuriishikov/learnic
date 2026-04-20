from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from learnic.infrastructure.configs import Configs, load_configs
from learnic.presentation.http.routes.root import router as root_router

_STATIC_DIR = Path(__file__).parent / "static"


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI) -> None:
    app.include_router(root_router)
    app.mount(
        "/",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )


def setup_map_tables() -> None:
    pass
