from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.cohort.ids import CohortID, WebinarSessionID
from learnic.entities.cohort.session import WebinarSession
from learnic.entities.product.value_objects import (
    StreamUrl,
    WebinarSessionDuration,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddOneOffWebinarSessionCommand:
    actor_id: UserID
    cohort_id: CohortID
    starts_at: datetime
    duration_minutes: int
    stream_url: str | None


@final
class AddOneOffWebinarSessionCommandHandler:
    """Adds a manual one-off session (``schedule_id`` ``None``)."""

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        cohort_gateway: CohortGateway,
        product_gateway: ProductGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._cohort_gateway: Final = cohort_gateway
        self._product_gateway: Final = product_gateway

    async def run(
        self,
        data: AddOneOffWebinarSessionCommand,
    ) -> WebinarSessionID:
        cohort = await self._cohort_gateway.with_id(data.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(data.cohort_id)
        await assert_cohort_authorized(
            cohort,
            data.actor_id,
            self._product_gateway,
        )
        session = WebinarSession.create(
            cohort_id=data.cohort_id,
            original_starts_at=data.starts_at,
            duration_minutes=WebinarSessionDuration(data.duration_minutes),
            schedule_id=None,
            stream_url=(
                StreamUrl(data.stream_url) if data.stream_url is not None else None
            ),
        )
        self._entity_saver.add_one(session)
        await self._transaction.commit()
        return session.oid
