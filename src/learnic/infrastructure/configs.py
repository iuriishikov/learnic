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
    verify_email_token_ttl_seconds: int = 60 * 60
    reset_password_token_ttl_seconds: int = 3600
    cookie_domain: str | None = None
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    frontend_base_url: str


class WebPushConfig(BaseSettings):
    """VAPID identity for outgoing Web Push deliveries.

    The keypair is generated once per environment with
    ``vapid --gen`` (or any compliant tool); only the PEM-encoded
    private key is stored here. The matching public key — the
    browser's ``applicationServerKey``, served by
    ``GET /web-push/vapid-public-key`` — is derived from this private
    key at runtime, so the public value can never drift from the
    private one. The backend signs each push request with the private
    key; the frontend subscribes with the derived public key.

    ``subject`` is the contact identifier required by the VAPID
    spec — typically a ``mailto:`` URL of the on-call address.
    Push services include it on abuse reports.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEBPUSH_", env_file=".env", extra="ignore"
    )

    vapid_private_key: str = ""
    vapid_subject: str = "mailto:noreply@learnic.local"


class AppConfig(BaseSettings):
    """Top-level deployment flags that gate environment-specific routes.

    Currently only ``environment`` lives here; the value drives the
    ``/dev/...`` router registration in :func:`bootstrap.setup_routes`
    so dev-only endpoints physically do not exist in production
    builds.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    environment: Literal["development", "staging", "production"] = "production"


class RecommendationsConfig(BaseSettings):
    """Ranking weights and popularity window for ``/users/me/recommended-products``.

    Weights are linear blend coefficients on max-scaled signals;
    ratios are what matters, not absolute values. Defaults below
    are a sensible starting prior — tune via env once conversion
    data is collected.
    """

    model_config = SettingsConfigDict(
        env_prefix="RECOMMENDATIONS_", env_file=".env", extra="ignore"
    )

    weight_tag: float = 0.40
    weight_author: float = 0.15
    weight_popularity: float = 0.30
    weight_freshness: float = 0.15
    popularity_window_days: int = 30


class Configs:
    __slots__ = (
        "postgres",
        "asgi",
        "s3",
        "taskiq",
        "redis",
        "rusender",
        "security",
        "web_push",
        "app",
        "recommendations",
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
        web_push: WebPushConfig,
        app: AppConfig,
        recommendations: RecommendationsConfig,
    ) -> None:
        self.postgres = postgres
        self.asgi = asgi
        self.s3 = s3
        self.taskiq = taskiq
        self.redis = redis
        self.rusender = rusender
        self.security = security
        self.web_push = web_push
        self.app = app
        self.recommendations = recommendations


def load_configs() -> Configs:
    return Configs(
        postgres=PostgresConfig(),  # pyright: ignore[reportCallIssue]
        asgi=ASGIConfig(),  # pyright: ignore[reportCallIssue]
        s3=S3Config(),  # pyright: ignore[reportCallIssue]
        taskiq=TaskIQConfig(),  # pyright: ignore[reportCallIssue]
        redis=RedisConfig(),  # pyright: ignore[reportCallIssue]
        rusender=RusenderConfig(),  # pyright: ignore[reportCallIssue]
        security=SecurityConfig(),  # pyright: ignore[reportCallIssue]
        web_push=WebPushConfig(),  # pyright: ignore[reportCallIssue]
        app=AppConfig(),  # pyright: ignore[reportCallIssue]
        recommendations=RecommendationsConfig(),  # pyright: ignore[reportCallIssue]
    )
