from typing import Literal

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
        return f"{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

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

    host: str
    port: int


class S3Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="S3_", env_file=".env", extra="ignore")

    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    region: str = "us-east-1"


class TaskIQConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TASKIQ_", env_file=".env", extra="ignore"
    )

    broker_url: str = "redis://localhost:6379/0"
    result_backend_url: str = "redis://localhost:6379/1"
    in_memory: bool = False
    workers: int = 2


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_", env_file=".env", extra="ignore"
    )

    url: str = "redis://localhost:6379/2"


class RusenderConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RUSENDER_", env_file=".env", extra="ignore"
    )

    api_key: str
    from_email: str
    from_name: str = ""


class SecurityConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_", env_file=".env", extra="ignore"
    )

    jwt_secret: str
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 30 * 24 * 3600
    signup_session_ttl_seconds: int = 30 * 60
    verify_email_token_ttl_seconds: int = 24 * 3600
    reset_password_token_ttl_seconds: int = 3600
    cookie_domain: str | None = None
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    frontend_base_url: str


class Configs:
    __slots__ = (
        "postgres",
        "asgi",
        "s3",
        "taskiq",
        "redis",
        "rusender",
        "security",
    )

    def __init__(
        self,
        postgres: PostgresConfig,
        asgi: ASGIConfig,
        s3: S3Config,
        taskiq: TaskIQConfig,
        redis: RedisConfig,
        rusender: RusenderConfig,
        security: SecurityConfig,
    ) -> None:
        self.postgres = postgres
        self.asgi = asgi
        self.s3 = s3
        self.taskiq = taskiq
        self.redis = redis
        self.rusender = rusender
        self.security = security


def load_configs() -> Configs:
    return Configs(
        postgres=PostgresConfig(),  # pyright: ignore[reportCallIssue]
        asgi=ASGIConfig(),  # pyright: ignore[reportCallIssue]
        s3=S3Config(),  # pyright: ignore[reportCallIssue]
        taskiq=TaskIQConfig(),  # pyright: ignore[reportCallIssue]
        redis=RedisConfig(),  # pyright: ignore[reportCallIssue]
        rusender=RusenderConfig(),  # pyright: ignore[reportCallIssue]
        security=SecurityConfig(),  # pyright: ignore[reportCallIssue]
    )
