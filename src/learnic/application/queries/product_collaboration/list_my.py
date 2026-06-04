from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationReader,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product_collaboration.list_for_product import (
    ProductCollaborationOutput,
    resolve_collaboration_output,
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

    def __init__(
        self,
        reader: ProductCollaborationReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: ListMyCollaborationsQuery,
    ) -> list[ProductCollaborationOutput]:
        views = await self._reader.for_user(
            data.actor_id,
            data.pagination,
        )
        return [
            await resolve_collaboration_output(view, self._file_storage)
            for view in views
        ]
