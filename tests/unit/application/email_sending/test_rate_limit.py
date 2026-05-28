import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.common.email.rate_limit import (
    EmailSendRateLimiter,
)
from learnic.application.common.errors import (
    EmailSendRateLimitExceededError,
)
from learnic.entities.email_sending.constants import (
    EMAIL_SEND_RATE_LIMIT_WINDOW,
    IP_MAX_LEN,
    MAX_EMAILS_PER_USER,
)
from learnic.entities.email_sending.models import EmailSending
from learnic.entities.user.models import UserID


def _limiter(
    count: int,
) -> tuple[EmailSendRateLimiter, AsyncMock, MagicMock]:
    gateway = AsyncMock()
    gateway.count_since.return_value = count
    entity_saver = MagicMock()
    limiter = EmailSendRateLimiter(gateway, entity_saver)
    return limiter, gateway, entity_saver


@pytest.mark.asyncio
async def test_records_send_when_below_cap() -> None:
    limiter, gateway, entity_saver = _limiter(MAX_EMAILS_PER_USER - 1)
    actor = UserID(uuid.uuid4())

    await limiter.register(
        actor_id=actor,
        recipient="to@example.com",
        ip="203.0.113.7",
    )

    gateway.acquire_actor_lock.assert_awaited_once_with(actor)
    entity_saver.add_one.assert_called_once()
    record = entity_saver.add_one.call_args.args[0]
    assert isinstance(record, EmailSending)
    assert record.actor_id == actor
    assert record.recipient == "to@example.com"
    assert record.ip == "203.0.113.7"


@pytest.mark.asyncio
async def test_refuses_when_at_cap() -> None:
    limiter, _gateway, entity_saver = _limiter(MAX_EMAILS_PER_USER)
    actor = UserID(uuid.uuid4())

    with pytest.raises(EmailSendRateLimitExceededError) as excinfo:
        await limiter.register(
            actor_id=actor,
            recipient="to@example.com",
            ip=None,
        )

    assert excinfo.value.actor_id == actor
    assert excinfo.value.limit == MAX_EMAILS_PER_USER
    assert excinfo.value.retry_after_seconds == int(
        EMAIL_SEND_RATE_LIMIT_WINDOW.total_seconds(),
    )
    entity_saver.add_one.assert_not_called()


@pytest.mark.asyncio
async def test_acquires_lock_before_counting() -> None:
    # The advisory lock must be taken *before* the count read; if the
    # order were reversed, two concurrent sends could both read the
    # same stale count and both slip past the cap.
    order: list[str] = []
    gateway = AsyncMock()
    gateway.acquire_actor_lock.side_effect = lambda *_a, **_k: order.append("lock")

    def _count(*_a: object, **_k: object) -> int:
        order.append("count")
        return 0

    gateway.count_since.side_effect = _count
    limiter = EmailSendRateLimiter(gateway, MagicMock())

    await limiter.register(
        actor_id=UserID(uuid.uuid4()),
        recipient="to@example.com",
        ip=None,
    )

    assert order == ["lock", "count"]


@pytest.mark.asyncio
async def test_truncates_overlong_ip() -> None:
    limiter, _gateway, entity_saver = _limiter(0)

    await limiter.register(
        actor_id=UserID(uuid.uuid4()),
        recipient="to@example.com",
        ip="9" * 200,
    )

    record = entity_saver.add_one.call_args.args[0]
    assert record.ip is not None
    assert len(record.ip) == IP_MAX_LEN
