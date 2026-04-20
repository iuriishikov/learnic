from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_", env_file=".env", extra="ignore"
    )

    user: str
    password: str
    host: str
    port: int = 5432
    db: str
    debug: bool = Field(default=False, validation_alias="SQLALCHEMY_DEBUG")

    @property
    def _credentials(self) -> str:
        return (
            f"{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
        )

    @property
    def dsn_async(self) -> str:
        return f"postgresql+asyncpg://{self._credentials}"

    @property
    def dsn_sync(self) -> str:
        return f"postgresql+psycopg://{self._credentials}"


class ASGIConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UVICORN_", env_file=".env", extra="ignore"
    )

    host: str = "0.0.0.0"
    port: int = 8000


class Configs:
    __slots__ = ("postgres", "asgi")

    def __init__(self, postgres: PostgresConfig, asgi: ASGIConfig) -> None:
        self.postgres = postgres
        self.asgi = asgi


def load_configs() -> Configs:
    return Configs(
        postgres=PostgresConfig(),  # pyright: ignore[reportCallIssue]
        asgi=ASGIConfig(),  # pyright: ignore[reportCallIssue]
    )