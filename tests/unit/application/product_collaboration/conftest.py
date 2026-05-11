import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.entities.product.ids import ProductID
from learnic.infrastructure.configs import SecurityConfig
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import ScopeType
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    az = AsyncMock()
    az.require = AsyncMock()
    az.effective_permissions = AsyncMock(return_value=None)
    return az


@pytest.fixture
def fake_hierarchy() -> AsyncMock:
    """Permissive hierarchy mock — actor is treated as the owner."""
    hier = AsyncMock()
    hier.actor_position = AsyncMock(return_value=0)
    hier.require_can_assign_roles = AsyncMock()
    hier.require_can_act_on_user = AsyncMock()
    return hier


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
def fake_collab_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.active_for_product_and_user = AsyncMock(return_value=None)
    gw.pending_for_product_and_email = AsyncMock(return_value=None)
    gw.count_email_invites_by_actor_since = AsyncMock(return_value=0)
    return gw


@pytest.fixture
def fake_collab_saver() -> AsyncMock:
    saver = AsyncMock()
    saver.save = AsyncMock()
    saver.replace_grants = AsyncMock()
    return saver


@pytest.fixture
def fake_role_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.with_name_for_product = AsyncMock(return_value=None)
    gw.is_in_use = AsyncMock(return_value=False)
    return gw


@pytest.fixture
def fake_lineage_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.lineage_for_lesson = AsyncMock(return_value=None)
    reader.lineage_for_module = AsyncMock(return_value=None)
    return reader


@pytest.fixture
def fake_scheduler() -> AsyncMock:
    sched = AsyncMock()
    sched.schedule_send_email = AsyncMock()
    return sched


@pytest.fixture
def fake_notifier() -> AsyncMock:
    """Stub ``Notifier`` for collab handlers that send transient notifications."""
    notifier = AsyncMock()
    notifier.send = AsyncMock()
    return notifier


@pytest.fixture
def security_config() -> SecurityConfig:
    return SecurityConfig(
        jwt_secret="test-secret-at-least-32-bytes-long!",
        frontend_base_url="http://0.0.0.0:8000",
        cookie_secure=False,
    )


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def fake_notifications() -> AsyncMock:
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    publisher.republish_for_collaboration = AsyncMock()
    return publisher


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def actor_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def invitee_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def product(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Demo"),
    )


@pytest.fixture
def product_id(product: Product) -> ProductID:
    return product.oid


@pytest.fixture
def role_id() -> RoleID:
    return RoleID(uuid.uuid4())


@pytest.fixture
def existing_collab(
    product_id: ProductID,
    role_id: RoleID,
    invitee_id: UserID,
    actor_id: UserID,
) -> ProductCollaboration:
    """A pending collaboration with a single product-scoped grant."""
    token = InviteToken("plain-token-value")
    return ProductCollaboration.invite_existing_user(
        product_id=product_id,
        collaborator_id=invitee_id,
        invited_by=actor_id,
        grants=[
            CollaborationGrant.create(
                role_id=role_id,
                scope_type=ScopeType.PRODUCT,
                scope_id=None,
            ),
        ],
        token=token,
    )


@pytest.fixture
def invitee_user(invitee_id: UserID) -> User:
    return User(
        oid=invitee_id,
        email=Email("invitee@example.com"),
        first_name=FirstName("In"),
        last_name=LastName("Vitee"),
        patronymic=None,
        password_hash=PasswordHash("hash"),
        email_verified=True,
    )


@pytest.fixture
def actor_user(actor_id: UserID) -> User:
    return User(
        oid=actor_id,
        email=Email("actor@example.com"),
        first_name=FirstName("Ac"),
        last_name=LastName("Tor"),
        patronymic=None,
        password_hash=PasswordHash("hash"),
        email_verified=True,
    )


# Re-exported for convenience in test bodies
__all__ = [
    "CollaborationGrant",
    "CollaborationStatus",
    "InviteToken",
    "ProductCollaboration",
    "ProductCollaborationID",
    "ScopeType",
    "datetime",
    "timedelta",
    "timezone",
]
