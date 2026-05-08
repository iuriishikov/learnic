from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotAWebinarError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.models import Cohort
from learnic.entities.cohort.value_objects import CohortName
from learnic.entities.product.enums import ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import ParticipantsLimit
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddCohortCommand:
    actor_id: UserID
    product_id: ProductID
    host_id: UserID
    starts_on: date
    name: str | None
    max_participants: int | None
    ends_on: date | None


@final
class AddCohortCommandHandler:
    """Creates a new cohort under a webinar product.

    Only the product's author may create cohorts; the chosen
    ``host_id`` is whichever user the author wants running the
    sessions (further role checks are deferred until a roles
    system exists).
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway

    async def run(self, data: AddCohortCommand) -> CohortID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id != data.actor_id:
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        if product.type is not ProductType.WEBINAR:
            raise NotAWebinarError(data.product_id)
        cohort = Cohort.create(
            webinar_id=data.product_id,
            host_id=data.host_id,
            starts_on=data.starts_on,
            name=(CohortName(data.name) if data.name is not None else None),
            max_participants=(
                ParticipantsLimit(data.max_participants)
                if data.max_participants is not None
                else None
            ),
            ends_on=data.ends_on,
        )
        self._entity_saver.add_one(cohort)
        await self._transaction.commit()
        return cohort.oid
