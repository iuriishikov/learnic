import uuid
from datetime import datetime, timedelta, timezone

import pytest

from learnic.entities.billing.errors import SubscriptionExpiryInPastError
from learnic.entities.billing.ids import SubscriptionID
from learnic.entities.billing.models import Subscription
from learnic.entities.billing.plan import BETA
from learnic.entities.user.models import UserID


def _user() -> UserID:
    return UserID(uuid.uuid4())


# ------------------------- create_subscription ------------------------- #


def test_create_subscription_indefinite_is_active() -> None:
    sub = Subscription.create_subscription(user_id=_user(), plan_code=BETA)

    assert sub.expires_at is None
    assert sub.revoked_at is None
    assert sub.plan_code == BETA
    assert sub.is_active() is True


def test_create_subscription_future_expiry_is_active() -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    sub = Subscription.create_subscription(
        user_id=_user(),
        plan_code=BETA,
        expires_at=expires,
    )

    assert sub.expires_at == expires
    assert sub.is_active() is True


def test_create_subscription_records_granting_admin() -> None:
    admin = _user()

    sub = Subscription.create_subscription(
        user_id=_user(),
        plan_code=BETA,
        granted_by=admin,
    )

    assert sub.granted_by == admin


def test_create_subscription_past_expiry_raises() -> None:
    past = datetime.now(timezone.utc) - timedelta(days=1)

    with pytest.raises(SubscriptionExpiryInPastError):
        Subscription.create_subscription(
            user_id=_user(),
            plan_code=BETA,
            expires_at=past,
        )


def test_create_subscription_expiry_at_now_raises() -> None:
    # The factory's own ``now`` is computed a hair after this value,
    # so an "expires == now" request lands at or before it and the
    # ``<= now`` guard rejects it.
    now_ish = datetime.now(timezone.utc)

    with pytest.raises(SubscriptionExpiryInPastError):
        Subscription.create_subscription(
            user_id=_user(),
            plan_code=BETA,
            expires_at=now_ish,
        )


def test_expiry_in_past_error_carries_field_metadata() -> None:
    err = SubscriptionExpiryInPastError()

    assert err.field == "expires_at"
    assert err.reason == "must_be_in_future"


# -------------------------------- revoke ------------------------------- #


def test_revoke_stamps_revoked_at_now_by_default() -> None:
    sub = Subscription.create_subscription(user_id=_user(), plan_code=BETA)

    before = datetime.now(timezone.utc)
    sub.revoke()

    assert sub.revoked_at is not None
    assert sub.revoked_at >= before
    assert sub.is_active() is False


def test_revoke_accepts_explicit_timestamp() -> None:
    sub = Subscription.create_subscription(user_id=_user(), plan_code=BETA)
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    sub.revoke(at=at)

    assert sub.revoked_at == at


# ------------------------------- is_active ----------------------------- #


_NOW = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("expires_at", "revoked_at", "expected"),
    [
        pytest.param(None, None, True, id="indefinite-unrevoked"),
        pytest.param(
            _NOW + timedelta(days=1), None, True, id="future-expiry",
        ),
        pytest.param(
            _NOW - timedelta(days=1), None, False, id="past-expiry",
        ),
        pytest.param(_NOW, None, False, id="expiry-equals-now"),
        pytest.param(None, _NOW - timedelta(days=1), False, id="revoked"),
        pytest.param(
            _NOW + timedelta(days=1),
            _NOW - timedelta(days=1),
            False,
            id="revoked-overrides-future-expiry",
        ),
    ],
)
def test_is_active_truth_table(
    expires_at: datetime | None,
    revoked_at: datetime | None,
    expected: bool,
) -> None:
    # Build the entity directly (not via the factory) so historical /
    # already-expired rows can be represented — loading those from the
    # DB must never raise, unlike minting via create_subscription.
    sub = Subscription(
        oid=SubscriptionID(uuid.uuid4()),
        user_id=_user(),
        plan_code=BETA,
        granted_at=_NOW - timedelta(days=10),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )

    assert sub.is_active(at=_NOW) is expected
