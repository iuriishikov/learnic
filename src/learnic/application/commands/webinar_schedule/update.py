from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_schedule_authorized,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleGateway,
)
from learnic.application.common.scheduling.recurrence import (
    RecurrenceRuleValidator,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.cohort.value_objects import (
    IanaTimezone,
    RecurrenceRule,
)
from learnic.entities.product.value_objects import WebinarSessionDuration
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateWebinarScheduleCommand:
    actor_id: UserID
    schedule_id: WebinarScheduleID
    timezone: str
    starts_on: date
    rrule: str
    duration_minutes: int
    ends_on: date | None


@final
class UpdateWebinarScheduleCommandHandler:
    """PUT-style replace of all schedule fields, then re-materialize.

    Past sessions are not retroactively rewritten; the
    materialization task picks up from the last
    ``original_starts_at`` cursor and adds new sessions according
    to the updated rule.
    """

    def __init__(
        self,
        transaction: Transaction,
        schedule_gateway: WebinarScheduleGateway,
        cohort_gateway: CohortGateway,
        product_gateway: ProductGateway,
        rule_validator: RecurrenceRuleValidator,
        task_scheduler: TaskScheduler,
    ) -> None:
        self._transaction: Final = transaction
        self._schedule_gateway: Final = schedule_gateway
        self._cohort_gateway: Final = cohort_gateway
        self._product_gateway: Final = product_gateway
        self._rule_validator: Final = rule_validator
        self._task_scheduler: Final = task_scheduler

    async def run(self, data: UpdateWebinarScheduleCommand) -> None:
        schedule = await self._schedule_gateway.with_id(data.schedule_id)
        if schedule is None:
            raise EntityNotFoundError(data.schedule_id)
        await assert_schedule_authorized(
            schedule,
            data.actor_id,
            self._cohort_gateway,
            self._product_gateway,
        )
        rrule = RecurrenceRule(data.rrule)
        self._rule_validator.validate(rrule, data.starts_on)
        schedule.change_timezone(IanaTimezone(data.timezone))
        schedule.change_dates(data.starts_on, data.ends_on)
        schedule.change_rrule(rrule)
        schedule.change_duration(
            WebinarSessionDuration(data.duration_minutes),
        )
        await self._transaction.commit()
        await self._task_scheduler.schedule_materialize_webinar_schedule(
            schedule.oid,
        )
