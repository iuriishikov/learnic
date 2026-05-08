from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleGateway,
)
from learnic.application.common.persistence.webinar_session import (
    WebinarSessionGateway,
)
from learnic.application.common.scheduling.materializer import (
    ScheduleMaterializer,
)
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.cohort.session import WebinarSession

DEFAULT_MATERIALIZE_LIMIT: Final = 30


@dataclass(slots=True, frozen=True)
class MaterializeWebinarScheduleCommand:
    schedule_id: WebinarScheduleID
    limit: int = DEFAULT_MATERIALIZE_LIMIT


@final
class MaterializeWebinarScheduleCommandHandler:
    """Expands a schedule's rrule into concrete :class:`WebinarSession` rows.

    Run by the TaskIQ worker (kicked from
    ``schedule_materialize_webinar_schedule``). Idempotent — uses
    ``last_original_starts_at`` as a cursor so re-runs don't
    duplicate sessions; a ``UNIQUE(schedule_id, original_starts_at)``
    constraint guards against races between concurrent workers.

    No actor authorization here — the task is dispatched by the
    application after the user already passed the host/author
    check that created or updated the schedule.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        schedule_gateway: WebinarScheduleGateway,
        session_gateway: WebinarSessionGateway,
        materializer: ScheduleMaterializer,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._schedule_gateway: Final = schedule_gateway
        self._session_gateway: Final = session_gateway
        self._materializer: Final = materializer

    async def run(
        self,
        data: MaterializeWebinarScheduleCommand,
    ) -> int:
        schedule = await self._schedule_gateway.with_id(data.schedule_id)
        if schedule is None:
            raise EntityNotFoundError(data.schedule_id)

        cursor = await self._session_gateway.last_original_starts_at(
            schedule.oid,
        )
        occurrences = self._materializer.materialize(
            rule=schedule.rrule,
            tz=schedule.timezone,
            starts_on=schedule.starts_on,
            ends_on=schedule.ends_on,
            after=cursor,
            limit=data.limit,
        )
        for occurrence in occurrences:
            session = WebinarSession.create(
                cohort_id=schedule.cohort_id,
                original_starts_at=occurrence,
                duration_minutes=schedule.duration_minutes,
                schedule_id=schedule.oid,
            )
            self._entity_saver.add_one(session)
        await self._transaction.commit()
        return len(occurrences)
