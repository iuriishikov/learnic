from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from learnic.infrastructure.configs import Configs, load_configs
from learnic.infrastructure.persistence.models.file import map_file_table
from learnic.infrastructure.persistence.models.user import map_user_table
from learnic.presentation.http.routes.auth import router as auth_router
from learnic.presentation.http.routes.root import router as root_router
from learnic.presentation.http.routes.user import router as user_router

_STATIC_DIR = Path(__file__).parent / "static"


def setup_configs() -> Configs:
    return load_configs()


def setup_routes(app: FastAPI) -> None:
    app.include_router(root_router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.mount(
        "/",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )


def setup_map_tables() -> None:
    map_user_table()
    map_file_table()
