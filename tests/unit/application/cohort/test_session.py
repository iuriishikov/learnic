from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.webinar_session.add_one_off import (
    AddOneOffWebinarSessionCommand,
    AddOneOffWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.attach_recording import (
    AttachWebinarSessionRecordingCommand,
    AttachWebinarSessionRecordingCommandHandler,
)
from learnic.application.commands.webinar_session.cancel import (
    CancelWebinarSessionCommand,
    CancelWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.complete import (
    CompleteWebinarSessionCommand,
    CompleteWebinarSessionCommandHandler,
)
from learnic.application.commands.webinar_session.reschedule import (
    RescheduleWebinarSessionCommand,
    RescheduleWebinarSessionCommandHandler,
)
from learnic.application.common.errors import InsufficientPermissionsError
from learnic.entities.cohort.enums import WebinarSessionStatus
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.product.value_objects import WebinarSessionDuration
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_session_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    return g


@pytest.fixture
def existing_session(cohort: Cohort) -> WebinarSession:
    return WebinarSession.create(
        cohort_id=cohort.oid,
        original_starts_at=datetime(
            2026,
            9,
            4,
            16,
            0,
            tzinfo=timezone.utc,
        ),
        duration_minutes=WebinarSessionDuration(90),
    )


async def test_add_one_off_session_persists_and_returns_id(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = AddOneOffWebinarSessionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    starts_at = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)
    session_id = await handler.run(
        AddOneOffWebinarSessionCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            starts_at=starts_at,
            duration_minutes=90,
            stream_url=None,
        ),
    )

    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, WebinarSession)
    assert saved.oid == session_id
    assert saved.cohort_id == cohort.oid
    assert saved.schedule_id is None
    assert saved.original_starts_at == starts_at
    fake_transaction.commit.assert_awaited_once()


async def test_reschedule_session_updates_starts_at_and_status(
    fake_transaction: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_session: WebinarSession,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_session_gateway.with_id.return_value = existing_session
    fake_cohort_gateway.with_id.return_value = cohort
    handler = RescheduleWebinarSessionCommandHandler(
        transaction=fake_transaction,
        session_gateway=fake_session_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    new_start = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)
    await handler.run(
        RescheduleWebinarSessionCommand(
            actor_id=host_id,
            session_id=existing_session.oid,
            starts_at=new_start,
        ),
    )
    assert existing_session.starts_at == new_start
    assert existing_session.status is WebinarSessionStatus.RESCHEDULED


async def test_cancel_session_with_reason(
    fake_transaction: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_session: WebinarSession,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_session_gateway.with_id.return_value = existing_session
    fake_cohort_gateway.with_id.return_value = cohort
    handler = CancelWebinarSessionCommandHandler(
        transaction=fake_transaction,
        session_gateway=fake_session_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        CancelWebinarSessionCommand(
            actor_id=host_id,
            session_id=existing_session.oid,
            reason="Host illness",
        ),
    )
    assert existing_session.status is WebinarSessionStatus.CANCELLED
    assert existing_session.cancellation_reason is not None
    assert existing_session.cancellation_reason.value == "Host illness"


async def test_complete_session_sets_status(
    fake_transaction: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_session: WebinarSession,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_session_gateway.with_id.return_value = existing_session
    fake_cohort_gateway.with_id.return_value = cohort
    handler = CompleteWebinarSessionCommandHandler(
        transaction=fake_transaction,
        session_gateway=fake_session_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        CompleteWebinarSessionCommand(
            actor_id=host_id,
            session_id=existing_session.oid,
        ),
    )
    assert existing_session.status is WebinarSessionStatus.COMPLETED


async def test_attach_recording_sets_url(
    fake_transaction: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_session: WebinarSession,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_session_gateway.with_id.return_value = existing_session
    fake_cohort_gateway.with_id.return_value = cohort
    handler = AttachWebinarSessionRecordingCommandHandler(
        transaction=fake_transaction,
        session_gateway=fake_session_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        AttachWebinarSessionRecordingCommand(
            actor_id=host_id,
            session_id=existing_session.oid,
            url="https://recordings.example.com/x.mp4",
        ),
    )
    assert existing_session.recording_url is not None
    assert existing_session.recording_url.value == (
        "https://recordings.example.com/x.mp4"
    )


async def test_session_action_by_stranger_raises(
    fake_transaction: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_session: WebinarSession,
    cohort: Cohort,
    stranger_id: UserID,
) -> None:
    fake_session_gateway.with_id.return_value = existing_session
    fake_cohort_gateway.with_id.return_value = cohort
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=stranger_id,
        product_id=cohort.webinar_id,
        permission="MANAGE_RELEASES",
    )
    handler = CompleteWebinarSessionCommandHandler(
        transaction=fake_transaction,
        session_gateway=fake_session_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            CompleteWebinarSessionCommand(
                actor_id=stranger_id,
                session_id=existing_session.oid,
            ),
        )
    fake_transaction.commit.assert_not_called()
