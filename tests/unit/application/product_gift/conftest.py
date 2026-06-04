import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)
from learnic.infrastructure.configs import SecurityConfig


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    # ``EntitySaver.add_one`` is synchronous — use a plain Mock so the
    # call is not treated as an awaitable.
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    az = AsyncMock()
    az.require = AsyncMock()
    return az


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.with_email = AsyncMock(return_value=None)
    return gw


@pytest.fixture
def fake_gift_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.active_for_product_and_user = AsyncMock(return_value=None)
    gw.pending_for_product_and_email = AsyncMock(return_value=None)
    gw.count_email_invites_by_actor_since = AsyncMock(return_value=0)
    gw.delete_expired_pending_invites = AsyncMock(return_value=0)
    return gw


@pytest.fixture
def fake_notifier() -> AsyncMock:
    notifier = AsyncMock()
    notifier.send = AsyncMock()
    return notifier


@pytest.fixture
def fake_scheduler() -> AsyncMock:
    sched = AsyncMock()
    sched.schedule_send_email = AsyncMock()
    return sched


@pytest.fixture
def fake_notifications() -> AsyncMock:
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    publisher.republish_for_gift = AsyncMock()
    return publisher


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def fake_enrollment_service() -> AsyncMock:
    service = AsyncMock()
    service.enroll = AsyncMock(return_value=EnrollmentID(uuid.uuid4()))
    return service


@pytest.fixture
def security_config() -> SecurityConfig:
    return SecurityConfig(
        jwt_secret="test-secret-at-least-32-bytes-long!",
        frontend_base_url="https://learnic.ru",
        cookie_secure=False,
    )


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def actor_id() -> UserID:
    """The gifter."""
    return UserID(uuid.uuid4())


@pytest.fixture
def recipient_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def product(author_id: UserID) -> Product:
    note = Product.create_note(
        author_id=author_id,
        name=ProductTitle("Demo note"),
    )
    note.publish()
    return note


@pytest.fixture
def product_id(product: Product) -> ProductID:
    return product.oid


@pytest.fixture
def recipient_user(recipient_id: UserID) -> User:
    return User(
        oid=recipient_id,
        email=Email("recipient@example.com"),
        first_name=FirstName("Re"),
        last_name=LastName("Cipient"),
        patronymic=None,
        password_hash=PasswordHash("hash"),
        email_verified=True,
    )


@pytest.fixture
def gift_token() -> InviteToken:
    return InviteToken("plain-gift-token-value")


@pytest.fixture
def pending_gift(
    product_id: ProductID,
    recipient_id: UserID,
    actor_id: UserID,
    gift_token: InviteToken,
) -> ProductGift:
    return ProductGift.invite_existing_user(
        product_id=product_id,
        recipient_id=recipient_id,
        invited_by=actor_id,
        token=gift_token,
    )


__all__ = [
    "EnrollmentID",
    "InviteToken",
    "ProductGift",
    "ProductGiftID",
]
