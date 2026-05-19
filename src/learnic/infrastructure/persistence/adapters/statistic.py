from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.statistic import (
    StatisticGateway,
)
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.models.statistic import (
    statistics_table,
)
from learnic.infrastructure.statistics.specs._spec import (
    StatisticTypeRegistry,
)


class StatisticMapperAlchemy(StatisticGateway):
    """Postgres implementation of :class:`StatisticGateway`.

    Inserts the parent ``statistics`` row and the matching
    subtype row through SA Core in the same caller transaction.
    The per-type ``INSERT`` payload is delegated to the spec
    resolved from :class:`StatisticTypeRegistry` by the details
    class of the incoming entity — adding a new type therefore
    never touches this class.
    """

    def __init__(
        self,
        session: AsyncSession,
        type_registry: StatisticTypeRegistry,
    ) -> None:
        self._session: Final = session
        self._types: Final = type_registry

    @override
    async def add(self, statistic: Statistic) -> None:
        spec = self._types.by_details_type(type(statistic.details))
        await self._session.execute(
            sa.insert(statistics_table).values(
                oid=statistic.oid,
                type=statistic.type.value,
                actor_id=statistic.actor_id,
                created_at=statistic.created_at,
            ),
        )
        await self._session.execute(
            sa.insert(spec.table).values(
                spec.insert_values(statistic, statistic.details),
            ),
        )
