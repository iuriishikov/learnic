from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.scheduling.recurrence import (
    RecurrenceRuleValidator,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.cohort.ids import CohortID, WebinarScheduleID
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)
from learnic.entities.product.value_objects import WebinarSessionDuration
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddWebinarScheduleCommand:
    actor_id: UserID
    cohort_id: CohortID
    timezone: str
    starts_on: date
    rrule: str
    duration_minutes: int
    ends_on: date | None


@final
class AddWebinarScheduleCommandHandler:
    """Creates a new ``WebinarSchedule`` and enqueues materialization.

    Validates the rrule semantically (via
    :class:`RecurrenceRuleValidator`) before persisting, then kicks
    off ``schedule_materialize_webinar_schedule`` so the worker
    expands the rule into concrete :class:`WebinarSession` rows.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
        rule_validator: RecurrenceRuleValidator,
        task_scheduler: TaskScheduler,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer
        self._rule_validator: Final = rule_validator
        self._task_scheduler: Final = task_scheduler

    async def run(
        self,
        data: AddWebinarScheduleCommand,
    ) -> WebinarScheduleID:
        cohort = await self._cohort_gateway.with_id(data.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(data.cohort_id)
        await assert_cohort_authorized(
            cohort,
            data.actor_id,
            self._authorizer,
        )
        rrule = RecurrenceRule(data.rrule)
        self._rule_validator.validate(rrule, data.starts_on)
        schedule = WebinarSchedule.create(
            cohort_id=data.cohort_id,
            tz=IanaTimezone(data.timezone),
            starts_on=data.starts_on,
            rrule=rrule,
            duration_minutes=WebinarSessionDuration(data.duration_minutes),
            ends_on=data.ends_on,
        )
        self._entity_saver.add_one(schedule)
        await self._transaction.commit()
        await self._task_scheduler.schedule_materialize_webinar_schedule(
            schedule.oid,
        )
        return schedule.oid
