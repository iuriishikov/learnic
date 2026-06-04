"""Unit tests for EntitlementService delta-aware replace check.

The legacy ``ensure_can_upload`` is exercised indirectly through
the command handlers; the explicit tests here cover the new
:meth:`EntitlementService.ensure_can_replace_upload` because its
shrink-friendly semantics are not obvious from the signature and
were previously the source of false-rejects on the collage path.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.errors import StorageQuotaExceededError
from learnic.entities.user.models import UserID


_USER_ID = UserID(uuid.uuid4())
_TWO_GIB = 2 * 1024 * 1024 * 1024


async def test_pure_shrink_passes_even_when_over_cap(
    entitlement_service: EntitlementService,
    fake_file_usage_reader: AsyncMock,
) -> None:
    # Author is already at 100% of the FREE cap. A replace that
    # frees more bytes than it adds (shrink) must NOT raise — this
    # is the whole point of the delta-aware variant.
    fake_file_usage_reader.bytes_used_by_note_author.return_value = _TWO_GIB

    await entitlement_service.ensure_can_replace_upload(
        _USER_ID,
        added_bytes=500 * 1024 * 1024,
        freed_bytes=800 * 1024 * 1024,
    )
    # No assertion needed beyond "did not raise" — the StorageQuotaExceededError
    # would have surfaced if the check had used naive add-semantics.


async def test_replace_within_cap_passes(
    entitlement_service: EntitlementService,
    fake_file_usage_reader: AsyncMock,
) -> None:
    fake_file_usage_reader.bytes_used_by_note_author.return_value = (
        1024 * 1024 * 1024  # 1 GiB used out of 2 GiB cap
    )

    await entitlement_service.ensure_can_replace_upload(
        _USER_ID,
        added_bytes=200 * 1024 * 1024,
        freed_bytes=50 * 1024 * 1024,
    )


async def test_replace_over_cap_raises_with_effective_delta(
    entitlement_service: EntitlementService,
    fake_file_usage_reader: AsyncMock,
) -> None:
    # 1.9 GiB used. Replace adds 200 MB, frees 50 MB → effective
    # delta = 150 MB. 1.9 GiB + 150 MB > 2 GiB → should raise.
    fake_file_usage_reader.bytes_used_by_note_author.return_value = (
        int(1.9 * 1024 * 1024 * 1024)
    )
    added = 200 * 1024 * 1024
    freed = 50 * 1024 * 1024

    with pytest.raises(StorageQuotaExceededError) as exc_info:
        await entitlement_service.ensure_can_replace_upload(
            _USER_ID,
            added_bytes=added,
            freed_bytes=freed,
        )

    # The error reports the effective delta, not the raw added.
    assert exc_info.value.attempted_bytes == added - freed
    assert exc_info.value.limit_bytes == _TWO_GIB


async def test_replace_acquires_lock_before_reading_usage(
    entitlement_service: EntitlementService,
    fake_storage_quota_lock: AsyncMock,
    fake_file_usage_reader: AsyncMock,
) -> None:
    # The lock must be taken BEFORE used-bytes are read; otherwise
    # the TOCTOU window that this protocol exists to close stays open.
    call_order: list[str] = []
    fake_storage_quota_lock.acquire_for.side_effect = (
        lambda _: call_order.append("lock")
    )

    async def record_used(_: UserID) -> int:
        call_order.append("read_used")
        return 0

    fake_file_usage_reader.bytes_used_by_note_author.side_effect = (
        record_used
    )

    await entitlement_service.ensure_can_replace_upload(
        _USER_ID,
        added_bytes=1024,
        freed_bytes=0,
    )

    assert call_order == ["lock", "read_used"]
