import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.common.security.access_tokens import (
    AccessTokenPayload,
    IssuedAccessToken,
)
from learnic.application.common.security.refresh_tokens import (
    IssuedRefreshToken,
    RefreshTokenRecord,
)
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)
from learnic.infrastructure.configs import SecurityConfig


@pytest.fixture
def security_config() -> SecurityConfig:
    return SecurityConfig(
        jwt_secret="test-secret-at-least-32-bytes-long!",
        frontend_base_url="http://0.0.0.0:8000",
        cookie_secure=False,
    )


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    gateway.with_email = AsyncMock()
    return gateway


@pytest.fixture
def fake_hasher() -> MagicMock:
    hasher = MagicMock()
    hasher.hash = MagicMock(return_value=PasswordHash("hashed"))
    hasher.verify = MagicMock(return_value=True)
    hasher.needs_rehash = MagicMock(return_value=False)
    return hasher


@pytest.fixture
def fake_email_tokens() -> AsyncMock:
    store = AsyncMock()
    store.issue = AsyncMock(return_value="raw-email-token")
    store.consume = AsyncMock()
    return store


@pytest.fixture
def fake_signup_sessions() -> AsyncMock:
    store = AsyncMock()
    store.issue = AsyncMock(return_value="raw-signup-token")
    store.resolve = AsyncMock()
    store.revoke = AsyncMock()
    return store


@pytest.fixture
def fake_scheduler() -> AsyncMock:
    sch = AsyncMock()
    sch.schedule_send_email = AsyncMock()
    return sch


@pytest.fixture
def fake_access_tokens() -> MagicMock:
    svc = MagicMock()
    svc.issue = MagicMock(
        side_effect=lambda uid: IssuedAccessToken(
            token="jwt",
            payload=AccessTokenPayload(
                user_id=uid,
                jti=uuid.uuid4(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            ),
        )
    )
    svc.decode = MagicMock()
    return svc


@pytest.fixture
def fake_refresh_store() -> AsyncMock:
    store = AsyncMock()

    async def issue(user_id, family_id=None, device=None):  # noqa: ANN001
        return IssuedRefreshToken(
            token="raw-refresh",
            record=RefreshTokenRecord(
                jti=uuid.uuid4(),
                family_id=family_id or uuid.uuid4(),
                user_id=user_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            ),
        )

    store.issue = AsyncMock(side_effect=issue)
    store.rotate = AsyncMock()
    store.revoke_family = AsyncMock()
    store.revoke_family_for_user = AsyncMock(return_value=True)
    store.revoke_all_for_user = AsyncMock()
    store.resolve = AsyncMock()
    return store


@pytest.fixture
def fake_denylist() -> AsyncMock:
    dl = AsyncMock()
    dl.is_denied = AsyncMock(return_value=False)
    dl.deny = AsyncMock()
    dl.cleanup_expired = AsyncMock(return_value=0)
    return dl


@pytest.fixture
def verified_user() -> User:
    return User(
        oid=UserID(uuid.uuid4()),
        email=Email("user@example.com"),
        first_name=FirstName("Ivan"),
        last_name=LastName("Ivanov"),
        patronymic=None,
        password_hash=PasswordHash("hashed"),
        email_verified=True,
    )


@pytest.fixture
def unverified_user() -> User:
    return User(
        oid=UserID(uuid.uuid4()),
        email=Email("user@example.com"),
        first_name=FirstName("Ivan"),
        last_name=LastName("Ivanov"),
        patronymic=None,
        password_hash=PasswordHash("hashed"),
        email_verified=False,
    )
