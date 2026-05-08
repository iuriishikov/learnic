from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.value_objects import CohortName
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateCohortNameCommand:
    actor_id: UserID
    cohort_id: CohortID
    value: str | None


@final
class UpdateCohortNameCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        cohort_gateway: CohortGateway,
        product_gateway: ProductGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._cohort_gateway: Final = cohort_gateway
        self._product_gateway: Final = product_gateway

    async def run(self, data: UpdateCohortNameCommand) -> None:
        cohort = await self._cohort_gateway.with_id(data.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(data.cohort_id)
        await assert_cohort_authorized(
            cohort,
            data.actor_id,
            self._product_gateway,
        )
        cohort.rename(
            CohortName(data.value) if data.value is not None else None,
        )
        await self._transaction.commit()
