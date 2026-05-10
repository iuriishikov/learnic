from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_schedule_authorized,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleGateway,
)
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteWebinarScheduleCommand:
    actor_id: UserID
    schedule_id: WebinarScheduleID


@final
class DeleteWebinarScheduleCommandHandler:
    """Removes a schedule. Existing sessions become orphan (``schedule_id`` SET NULL).

    Past materialised sessions survive the delete via the
    ``ON DELETE SET NULL`` FK on ``webinar_sessions.schedule_id``;
    cancellations of those orphan sessions stay the host's
    responsibility.
    """

    def __init__(
        self,
        transaction: Transaction,
        schedule_gateway: WebinarScheduleGateway,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._schedule_gateway: Final = schedule_gateway
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: DeleteWebinarScheduleCommand) -> None:
        schedule = await self._schedule_gateway.with_id(data.schedule_id)
        if schedule is None:
            raise EntityNotFoundError(data.schedule_id)
        await assert_schedule_authorized(
            schedule,
            data.actor_id,
            self._cohort_gateway,
            self._authorizer,
        )
        await self._schedule_gateway.delete(schedule)
        await self._transaction.commit()
