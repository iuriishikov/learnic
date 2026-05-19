import uuid
from datetime import datetime, timedelta, timezone

import pytest

from learnic.entities.wallet.enums import FreezeSource, FreezeStatus
from learnic.entities.wallet.errors import FreezeAlreadyResolvedError
from learnic.entities.wallet.ids import WalletID
from learnic.entities.wallet.models import FreezeEntry
from learnic.entities.wallet.value_objects import MinorAmount


def _wallet_id() -> WalletID:
    return WalletID(uuid.uuid4())


def _make_freeze() -> FreezeEntry:
    now = datetime.now(timezone.utc)
    return FreezeEntry.create(
        wallet_id=_wallet_id(),
        amount=MinorAmount(500_00),
        source=FreezeSource.SALE_HOLD,
        frozen_at=now,
        unfreeze_at=now + timedelta(days=14),
    )


class TestCreate:
    def test_starts_frozen(self) -> None:
        assert _make_freeze().status is FreezeStatus.FROZEN

    def test_resolved_at_starts_none(self) -> None:
        assert _make_freeze().resolved_at is None


class TestRelease:
    def test_releases_a_frozen_entry(self) -> None:
        freeze = _make_freeze()
        at = datetime.now(timezone.utc)
        freeze.release(at)
        assert freeze.status is FreezeStatus.RELEASED
        assert freeze.resolved_at == at

    def test_release_twice_raises(self) -> None:
        freeze = _make_freeze()
        freeze.release(datetime.now(timezone.utc))
        with pytest.raises(FreezeAlreadyResolvedError) as exc:
            freeze.release(datetime.now(timezone.utc))
        assert exc.value.current_status == "released"

    def test_release_after_cancel_raises(self) -> None:
        freeze = _make_freeze()
        freeze.cancel(datetime.now(timezone.utc))
        with pytest.raises(FreezeAlreadyResolvedError) as exc:
            freeze.release(datetime.now(timezone.utc))
        assert exc.value.current_status == "cancelled"


class TestCancel:
    def test_cancels_a_frozen_entry(self) -> None:
        freeze = _make_freeze()
        at = datetime.now(timezone.utc)
        freeze.cancel(at)
        assert freeze.status is FreezeStatus.CANCELLED
        assert freeze.resolved_at == at

    def test_cancel_twice_raises(self) -> None:
        freeze = _make_freeze()
        freeze.cancel(datetime.now(timezone.utc))
        with pytest.raises(FreezeAlreadyResolvedError):
            freeze.cancel(datetime.now(timezone.utc))

    def test_cancel_after_release_raises(self) -> None:
        freeze = _make_freeze()
        freeze.release(datetime.now(timezone.utc))
        with pytest.raises(FreezeAlreadyResolvedError):
            freeze.cancel(datetime.now(timezone.utc))
