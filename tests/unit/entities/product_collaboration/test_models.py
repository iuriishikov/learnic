import uuid
from datetime import datetime, timedelta, timezone

import pytest

from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_TTL_DAYS,
)
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.errors import (
    EmptyGrantsError,
    InviteTokenExpiredError,
    InviteTokenMismatchError,
    OperationNotAllowedInStatusError,
)
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import ScopeType
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Email


def _user() -> UserID:
    return UserID(uuid.uuid4())


def _product() -> ProductID:
    return ProductID(uuid.uuid4())


def _role_id() -> RoleID:
    return RoleID(uuid.uuid4())


def _grants() -> list[CollaborationGrant]:
    return [
        CollaborationGrant.create(
            role_id=_role_id(),
            scope_type=ScopeType.PRODUCT,
            scope_id=None,
        ),
    ]


class TestInviteExistingUser:
    def test_creates_pending_with_token_hash(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        assert collab.status is CollaborationStatus.PENDING_INVITE
        assert collab.invite_token_hash == token.hashed()
        assert collab.invite_expires_at is not None
        assert collab.invited_email is None

    def test_rejects_empty_grants(self) -> None:
        with pytest.raises(EmptyGrantsError):
            ProductCollaboration.invite_existing_user(
                product_id=_product(),
                collaborator_id=_user(),
                invited_by=_user(),
                grants=[],
                token=InviteToken("plain-token-value"),
            )

    def test_default_ttl(self) -> None:
        now = datetime.now(timezone.utc)
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=InviteToken("plain-token-value"),
            now=now,
        )
        expected = now + timedelta(days=INVITE_TOKEN_TTL_DAYS)
        assert collab.invite_expires_at == expected


class TestInviteByEmail:
    def test_creates_pending_email_invite(self) -> None:
        token = InviteToken("plain-token-value")
        email = Email("invited@example.com")
        collab = ProductCollaboration.invite_by_email(
            product_id=_product(),
            invited_email=email,
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        assert collab.status is CollaborationStatus.PENDING_INVITE
        assert collab.collaborator_id is None
        assert collab.invited_email == email
        assert collab.invite_token_hash == token.hashed()


class TestAccept:
    def _make_pending(
        self,
        *,
        token: InviteToken,
        ttl_days: int = INVITE_TOKEN_TTL_DAYS,
        now: datetime | None = None,
    ) -> ProductCollaboration:
        return ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
            ttl_days=ttl_days,
            now=now,
        )

    def test_accept_transitions_to_active(self) -> None:
        token = InviteToken("plain-token-value")
        collab = self._make_pending(token=token)
        accepting_user = _user()
        collab.accept(accepting_user, token)
        assert collab.status is CollaborationStatus.ACTIVE
        assert collab.collaborator_id == accepting_user
        assert collab.accepted_at is not None
        assert collab.invite_token_hash is None
        assert collab.invite_expires_at is None

    def test_accept_rejects_wrong_token(self) -> None:
        collab = self._make_pending(token=InviteToken("a" * 16))
        with pytest.raises(InviteTokenMismatchError):
            collab.accept(_user(), InviteToken("b" * 16))

    def test_accept_rejects_when_already_active(self) -> None:
        token = InviteToken("plain-token-value")
        collab = self._make_pending(token=token)
        collab.accept(_user(), token)
        with pytest.raises(OperationNotAllowedInStatusError):
            collab.accept(_user(), token)

    def test_accept_rejects_expired(self) -> None:
        token = InviteToken("plain-token-value")
        old = datetime.now(timezone.utc) - timedelta(days=30)
        collab = self._make_pending(
            token=token,
            ttl_days=14,
            now=old,
        )
        with pytest.raises(InviteTokenExpiredError):
            collab.accept(
                _user(),
                token,
                now=datetime.now(timezone.utc),
            )


class TestAcceptInApp:
    def _make_pending(
        self,
        *,
        token: InviteToken,
        ttl_days: int = INVITE_TOKEN_TTL_DAYS,
        now: datetime | None = None,
    ) -> ProductCollaboration:
        return ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
            ttl_days=ttl_days,
            now=now,
        )

    def test_accept_in_app_transitions_to_active_without_token(self) -> None:
        token = InviteToken("plain-token-value")
        collab = self._make_pending(token=token)
        accepting_user = _user()
        collab.accept_in_app(accepting_user)
        assert collab.status is CollaborationStatus.ACTIVE
        assert collab.collaborator_id == accepting_user
        assert collab.accepted_at is not None
        assert collab.invite_token_hash is None
        assert collab.invite_expires_at is None

    def test_accept_in_app_rejects_when_already_active(self) -> None:
        token = InviteToken("plain-token-value")
        collab = self._make_pending(token=token)
        collab.accept_in_app(_user())
        with pytest.raises(OperationNotAllowedInStatusError):
            collab.accept_in_app(_user())

    def test_accept_in_app_rejects_expired(self) -> None:
        token = InviteToken("plain-token-value")
        old = datetime.now(timezone.utc) - timedelta(days=30)
        collab = self._make_pending(token=token, ttl_days=14, now=old)
        with pytest.raises(InviteTokenExpiredError):
            collab.accept_in_app(_user(), now=datetime.now(timezone.utc))


class TestRevoke:
    def test_revokes_active_collaboration(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        collab.accept(_user(), token)
        collab.revoke()
        assert collab.status is CollaborationStatus.REVOKED
        assert collab.revoked_at is not None
        assert collab.invite_token_hash is None

    def test_revoking_pending_clears_token(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        collab.revoke()
        assert collab.status is CollaborationStatus.REVOKED
        assert collab.invite_token_hash is None
        assert collab.invite_expires_at is None

    def test_double_revoke_is_rejected(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        collab.revoke()
        with pytest.raises(OperationNotAllowedInStatusError):
            collab.revoke()


class TestReplaceGrants:
    def test_only_active_collaborations_can_replace(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        with pytest.raises(OperationNotAllowedInStatusError):
            collab.replace_grants(_grants())

    def test_active_replace_swaps_grants(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        collab.accept(_user(), token)
        new = _grants()
        collab.replace_grants(new)
        assert collab.grants == new

    def test_active_replace_rejects_empty(self) -> None:
        token = InviteToken("plain-token-value")
        collab = ProductCollaboration.invite_existing_user(
            product_id=_product(),
            collaborator_id=_user(),
            invited_by=_user(),
            grants=_grants(),
            token=token,
        )
        collab.accept(_user(), token)
        with pytest.raises(EmptyGrantsError):
            collab.replace_grants([])
