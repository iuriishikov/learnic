"""Tests for ``PurgeExpiredInvitesCommandHandler``.

The handler is a thin wrapper: build ``now``, hand it to the
gateway, commit. The interesting properties are (a) the moment
passed to the gateway is the actual call-time UTC moment (so the
TTL boundary matches ``ProductCollaboration.accept``'s validation
exactly) and (b) the transaction is committed even when nothing
was deleted, so the no-op pass leaves no dangling savepoint.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from learnic.application.commands.product_collaboration.purge_expired_invites import (  # noqa: E501
    PurgeExpiredInvitesCommand,
    PurgeExpiredInvitesCommandHandler,
)


async def test_run_passes_call_time_utc_to_gateway_and_commits(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
) -> None:
    fake_collab_gateway.delete_expired_pending_invites = AsyncMock(
        return_value=7,
    )
    handler = PurgeExpiredInvitesCommandHandler(
        transaction=fake_transaction,
        collaboration_gateway=fake_collab_gateway,
    )

    before = datetime.now(timezone.utc)
    summary = await handler.run(PurgeExpiredInvitesCommand())
    after = datetime.now(timezone.utc)

    fake_collab_gateway.delete_expired_pending_invites.assert_called_once()
    passed = (
        fake_collab_gateway.delete_expired_pending_invites
        .call_args.kwargs["expires_before"]
    )
    # The boundary must be tz-aware UTC and bracketed by the
    # actual call window — the cron's validity hinges on this
    # matching ``ProductCollaboration.accept``'s ``moment``.
    assert passed.tzinfo is timezone.utc
    assert before <= passed <= after

    fake_transaction.commit.assert_called_once()
    assert summary.deleted == 7


async def test_run_commits_and_reports_zero_when_no_rows_match(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
) -> None:
    fake_collab_gateway.delete_expired_pending_invites = AsyncMock(
        return_value=0,
    )
    handler = PurgeExpiredInvitesCommandHandler(
        transaction=fake_transaction,
        collaboration_gateway=fake_collab_gateway,
    )

    summary = await handler.run(PurgeExpiredInvitesCommand())

    fake_transaction.commit.assert_called_once()
    assert summary.deleted == 0
