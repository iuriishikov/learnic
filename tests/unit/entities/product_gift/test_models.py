import uuid
from datetime import datetime, timedelta, timezone

import pytest

from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.errors import (
    InviteTokenExpiredError,
    InviteTokenMismatchError,
    OperationNotAllowedInGiftStatusError,
)
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.user.models import UserID


def _pending() -> tuple[ProductGift, InviteToken, UserID]:
    token = InviteToken("a-gift-token")
    recipient = UserID(uuid.uuid4())
    gift = ProductGift.invite_existing_user(
        product_id=ProductID(uuid.uuid4()),
        recipient_id=recipient,
        invited_by=UserID(uuid.uuid4()),
        token=token,
    )
    return gift, token, recipient


def test_accept_with_valid_token_transitions_to_accepted() -> None:
    gift, token, recipient = _pending()
    gift.accept(recipient, token)
    assert gift.status is GiftStatus.ACCEPTED
    assert gift.accepted_at is not None
    assert gift.invite_token_hash is None
    assert gift.invite_expires_at is None


def test_accept_with_wrong_token_raises() -> None:
    gift, _token, recipient = _pending()
    with pytest.raises(InviteTokenMismatchError):
        gift.accept(recipient, InviteToken("wrong-token"))
    assert gift.status is GiftStatus.PENDING_INVITE


def test_accept_after_expiry_raises() -> None:
    gift, token, recipient = _pending()
    past = datetime.now(timezone.utc) + timedelta(days=999)
    with pytest.raises(InviteTokenExpiredError):
        gift.accept(recipient, token, now=past)
    assert gift.status is GiftStatus.PENDING_INVITE


def test_double_accept_forbidden_by_state_machine() -> None:
    gift, token, recipient = _pending()
    gift.accept(recipient, token)
    with pytest.raises(OperationNotAllowedInGiftStatusError):
        gift.accept_in_app(recipient)


def test_decline_then_accept_forbidden() -> None:
    gift, token, recipient = _pending()
    gift.decline_in_app(recipient)
    assert gift.status is GiftStatus.DECLINED
    with pytest.raises(OperationNotAllowedInGiftStatusError):
        gift.accept(recipient, token)


def test_revoke_only_from_pending() -> None:
    gift, token, recipient = _pending()
    gift.accept(recipient, token)
    with pytest.raises(OperationNotAllowedInGiftStatusError):
        gift.revoke()


def test_by_email_accept_binds_recipient() -> None:
    from learnic.entities.user.value_objects import Email

    token = InviteToken("email-gift-token")
    gift = ProductGift.invite_by_email(
        product_id=ProductID(uuid.uuid4()),
        invited_email=Email("friend@example.com"),
        invited_by=UserID(uuid.uuid4()),
        token=token,
    )
    assert gift.recipient_id is None
    accepting = UserID(uuid.uuid4())
    gift.accept(accepting, token)
    assert gift.recipient_id == accepting
    assert gift.status is GiftStatus.ACCEPTED
