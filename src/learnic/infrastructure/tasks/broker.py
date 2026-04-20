from taskiq import AsyncBroker, InMemoryBroker
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from learnic.infrastructure.configs import TaskIQConfig


def _build_broker(config: TaskIQConfig) -> AsyncBroker:
    if config.in_memory:
        return InMemoryBroker()
    backend: RedisAsyncResultBackend[object] = RedisAsyncResultBackend(
        redis_url=config.result_backend_url,
    )
    return ListQueueBroker(
        url=config.broker_url,
    ).with_result_backend(backend)


# Module-level broker: `@broker.task` decorators register on this
# instance at import time. The worker imports it as an ASGI-like
# entry point; the producer (FastAPI app) uses it via the scheduler
# adapter and manages its lifecycle in the app lifespan.
broker: AsyncBroker = _build_broker(
    TaskIQConfig(),  # pyright: ignore[reportCallIssue]
)
