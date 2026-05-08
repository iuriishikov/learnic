from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationReader,
    ProductCollaborationView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListMyCollaborationsQuery:
    actor_id: UserID
    pagination: Pagination


@final
class ListMyCollaborationsQueryHandler:
    """Returns collaborations the caller participates in.

    No authorizer check needed — the query is already self-scoped
    by ``actor_id``; users can always read their own collaborations.
    """

    def __init__(self, reader: ProductCollaborationReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: ListMyCollaborationsQuery,
    ) -> list[ProductCollaborationView]:
        return await self._reader.for_user(
            data.actor_id,
            data.pagination,
        )
