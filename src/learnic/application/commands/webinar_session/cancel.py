from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_session_authorized,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.webinar_session import (
    WebinarSessionGateway,
)
from learnic.entities.cohort.ids import WebinarSessionID
from learnic.entities.cohort.value_objects import CancellationReason
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CancelWebinarSessionCommand:
    actor_id: UserID
    session_id: WebinarSessionID
    reason: str | None


@final
class CancelWebinarSessionCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        session_gateway: WebinarSessionGateway,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
    ) -> None:
        self._transaction: Final = transaction
        self._session_gateway: Final = session_gateway
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer

    async def run(self, data: CancelWebinarSessionCommand) -> None:
        session = await self._session_gateway.with_id(data.session_id)
        if session is None:
            raise EntityNotFoundError(data.session_id)
        await assert_session_authorized(
            session,
            data.actor_id,
            self._cohort_gateway,
            self._authorizer,
        )
        session.cancel(
            CancellationReason(data.reason) if data.reason is not None else None,
        )
        await self._transaction.commit()
