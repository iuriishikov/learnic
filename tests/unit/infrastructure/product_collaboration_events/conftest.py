from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from redis.asyncio import Redis


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
