import os

os.environ.setdefault("TASKIQ_IN_MEMORY", "true")

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from learnic.infrastructure.configs import (
    ASGIConfig,
    Configs,
    PostgresConfig,
    S3Config,
    TaskIQConfig,
)
from learnic.web import create_app_tests


@pytest.fixture
def configs() -> Configs:
    return Configs(
        postgres=PostgresConfig(
            user="test",
            password="test",
            host="localhost",
            port=5432,
            db="test",
        ),
        asgi=ASGIConfig(host="127.0.0.1", port=8000),
        s3=S3Config(
            endpoint="http://localhost:9000",
            access_key="test",
            secret_key="test",
            bucket="test",
            region="us-east-1",
        ),
        taskiq=TaskIQConfig(in_memory=True),
    )


@pytest.fixture
async def client(configs: Configs) -> AsyncIterator[AsyncClient]:
    app = create_app_tests(configs)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client
