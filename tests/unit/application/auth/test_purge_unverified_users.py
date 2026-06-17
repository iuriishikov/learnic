"""Tests for ``PurgeUnverifiedUsersCommandHandler``.

The handler is a thin wrapper: build call-time ``now``, hand it to the
gateway, commit. The properties worth pinning are (a) the moment
passed to the gateway is the actual call-time UTC moment — so the
"is this token/session still live" check inside the gateway lines up
with the verify-token / signup-session TTL boundaries exactly — and
(b) the transaction is committed even when nothing was deleted, so a
no-op pass leaves no dangling savepoint.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from learnic.application.commands.auth.purge_unverified_users import (
    PurgeUnverifiedUsersCommand,
    PurgeUnverifiedUsersCommandHandler,
)


async def test_run_passes_call_time_utc_to_gateway_and_commits(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
) -> None:
    fake_user_gateway.delete_abandoned_unverified = AsyncMock(
        return_value=5,
    )
    handler = PurgeUnverifiedUsersCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
    )

    before = datetime.now(timezone.utc)
    summary = await handler.run(PurgeUnverifiedUsersCommand())
    after = datetime.now(timezone.utc)

    fake_user_gateway.delete_abandoned_unverified.assert_called_once()
    passed = fake_user_gateway.delete_abandoned_unverified.call_args.args[0]
    # The boundary must be tz-aware UTC and bracketed by the actual
    # call window — the sweep's correctness hinges on this matching the
    # token/session ``expires_at`` checks inside the gateway.
    assert passed.tzinfo is timezone.utc
    assert before <= passed <= after

    fake_transaction.commit.assert_called_once()
    assert summary.deleted == 5


async def test_run_commits_and_reports_zero_when_no_rows_match(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
) -> None:
    fake_user_gateway.delete_abandoned_unverified = AsyncMock(
        return_value=0,
    )
    handler = PurgeUnverifiedUsersCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
    )

    summary = await handler.run(PurgeUnverifiedUsersCommand())

    fake_transaction.commit.assert_called_once()
    assert summary.deleted == 0
