import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.webinar_schedule.add import (
    AddWebinarScheduleCommand,
    AddWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.delete import (
    DeleteWebinarScheduleCommand,
    DeleteWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.materialize import (
    MaterializeWebinarScheduleCommand,
    MaterializeWebinarScheduleCommandHandler,
)
from learnic.application.commands.webinar_schedule.update import (
    UpdateWebinarScheduleCommand,
    UpdateWebinarScheduleCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.entities.cohort.errors import InvalidRecurrenceRuleError
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)
from learnic.entities.product.value_objects import WebinarSessionDuration
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_schedule_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    g.delete = AsyncMock()
    return g


@pytest.fixture
def fake_session_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    g.last_original_starts_at = AsyncMock(return_value=None)
    return g


@pytest.fixture
def fake_rule_validator() -> MagicMock:
    v = MagicMock()
    v.validate = MagicMock(return_value=None)
    return v


@pytest.fixture
def fake_materializer() -> MagicMock:
    m = MagicMock()
    m.materialize = MagicMock(return_value=[])
    return m


@pytest.fixture
def fake_task_scheduler() -> AsyncMock:
    s = AsyncMock()
    s.schedule_materialize_webinar_schedule = AsyncMock()
    return s


@pytest.fixture
def schedule(cohort: Cohort) -> WebinarSchedule:
    return WebinarSchedule.create(
        cohort_id=cohort.oid,
        tz=IanaTimezone("Europe/Sofia"),
        starts_on=date(2026, 9, 1),
        rrule=RecurrenceRule("FREQ=WEEKLY;BYDAY=FR;BYHOUR=19"),
        duration_minutes=WebinarSessionDuration(90),
    )


async def test_add_schedule_validates_persists_and_kicks_task(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_rule_validator: MagicMock,
    fake_task_scheduler: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = AddWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
        rule_validator=fake_rule_validator,
        task_scheduler=fake_task_scheduler,
    )

    schedule_id = await handler.run(
        AddWebinarScheduleCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
            timezone="Europe/Sofia",
            starts_on=date(2026, 9, 1),
            rrule="FREQ=WEEKLY;BYDAY=FR;BYHOUR=19",
            duration_minutes=90,
            ends_on=None,
        ),
    )

    fake_rule_validator.validate.assert_called_once()
    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, WebinarSchedule)
    assert saved.oid == schedule_id
    fake_transaction.commit.assert_awaited_once()
    fake_task_scheduler.schedule_materialize_webinar_schedule.assert_awaited_once_with(
        schedule_id,
    )


async def test_add_schedule_rejects_invalid_rrule(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_rule_validator: MagicMock,
    fake_task_scheduler: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    fake_rule_validator.validate.side_effect = InvalidRecurrenceRuleError(
        "semantic",
    )
    handler = AddWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
        rule_validator=fake_rule_validator,
        task_scheduler=fake_task_scheduler,
    )

    with pytest.raises(InvalidRecurrenceRuleError):
        await handler.run(
            AddWebinarScheduleCommand(
                actor_id=host_id,
                cohort_id=cohort.oid,
                timezone="Europe/Sofia",
                starts_on=date(2026, 9, 1),
                rrule="FREQ=WEEKLY;BYDAY=ZZ",
                duration_minutes=90,
                ends_on=None,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_task_scheduler.schedule_materialize_webinar_schedule.assert_not_called()


async def test_add_schedule_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_rule_validator: MagicMock,
    fake_task_scheduler: AsyncMock,
    cohort: Cohort,
    stranger_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=stranger_id,
        product_id=cohort.webinar_id,
        permission="MANAGE_RELEASES",
    )
    handler = AddWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
        rule_validator=fake_rule_validator,
        task_scheduler=fake_task_scheduler,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddWebinarScheduleCommand(
                actor_id=stranger_id,
                cohort_id=cohort.oid,
                timezone="Europe/Sofia",
                starts_on=date(2026, 9, 1),
                rrule="FREQ=WEEKLY;BYDAY=FR",
                duration_minutes=90,
                ends_on=None,
            ),
        )
    fake_task_scheduler.schedule_materialize_webinar_schedule.assert_not_called()


async def test_update_schedule_replaces_and_kicks_task(
    fake_transaction: AsyncMock,
    fake_schedule_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_rule_validator: MagicMock,
    fake_task_scheduler: AsyncMock,
    schedule: WebinarSchedule,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_schedule_gateway.with_id.return_value = schedule
    fake_cohort_gateway.with_id.return_value = cohort
    handler = UpdateWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        schedule_gateway=fake_schedule_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
        rule_validator=fake_rule_validator,
        task_scheduler=fake_task_scheduler,
    )

    await handler.run(
        UpdateWebinarScheduleCommand(
            actor_id=host_id,
            schedule_id=schedule.oid,
            timezone="Europe/Berlin",
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 12, 1),
            rrule="FREQ=WEEKLY;BYDAY=MO",
            duration_minutes=120,
        ),
    )

    assert schedule.timezone.value == "Europe/Berlin"
    assert schedule.rrule.value == "FREQ=WEEKLY;BYDAY=MO"
    assert schedule.duration_minutes.value == 120
    fake_task_scheduler.schedule_materialize_webinar_schedule.assert_awaited_once_with(
        schedule.oid,
    )


async def test_delete_schedule_calls_gateway_delete(
    fake_transaction: AsyncMock,
    fake_schedule_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    schedule: WebinarSchedule,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_schedule_gateway.with_id.return_value = schedule
    fake_cohort_gateway.with_id.return_value = cohort
    handler = DeleteWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        schedule_gateway=fake_schedule_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        DeleteWebinarScheduleCommand(
            actor_id=host_id,
            schedule_id=schedule.oid,
        ),
    )

    fake_schedule_gateway.delete.assert_awaited_once_with(schedule)
    fake_transaction.commit.assert_awaited_once()


async def test_materialize_creates_sessions_from_occurrences(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_schedule_gateway: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_materializer: MagicMock,
    schedule: WebinarSchedule,
) -> None:
    fake_schedule_gateway.with_id.return_value = schedule
    fake_session_gateway.last_original_starts_at.return_value = None
    occurrences = [
        datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc),
    ]
    fake_materializer.materialize.return_value = occurrences
    handler = MaterializeWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        schedule_gateway=fake_schedule_gateway,
        session_gateway=fake_session_gateway,
        materializer=fake_materializer,
    )

    count = await handler.run(
        MaterializeWebinarScheduleCommand(schedule_id=schedule.oid),
    )

    assert count == 3
    assert fake_entity_saver.add_one.call_count == 3
    saved_first = fake_entity_saver.add_one.call_args_list[0].args[0]
    assert isinstance(saved_first, WebinarSession)
    assert saved_first.original_starts_at == occurrences[0]
    assert saved_first.schedule_id == schedule.oid
    fake_transaction.commit.assert_awaited_once()


async def test_materialize_with_cursor_passes_after(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_schedule_gateway: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_materializer: MagicMock,
    schedule: WebinarSchedule,
) -> None:
    fake_schedule_gateway.with_id.return_value = schedule
    cursor = datetime(2026, 9, 11, 16, 0, tzinfo=timezone.utc)
    fake_session_gateway.last_original_starts_at.return_value = cursor
    fake_materializer.materialize.return_value = []
    handler = MaterializeWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        schedule_gateway=fake_schedule_gateway,
        session_gateway=fake_session_gateway,
        materializer=fake_materializer,
    )

    await handler.run(
        MaterializeWebinarScheduleCommand(schedule_id=schedule.oid),
    )

    kwargs = fake_materializer.materialize.call_args.kwargs
    assert kwargs["after"] == cursor


async def test_materialize_missing_schedule_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_schedule_gateway: AsyncMock,
    fake_session_gateway: AsyncMock,
    fake_materializer: MagicMock,
) -> None:
    fake_schedule_gateway.with_id.return_value = None
    handler = MaterializeWebinarScheduleCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        schedule_gateway=fake_schedule_gateway,
        session_gateway=fake_session_gateway,
        materializer=fake_materializer,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            MaterializeWebinarScheduleCommand(
                schedule_id=WebinarScheduleID(uuid.uuid4()),
            ),
        )
