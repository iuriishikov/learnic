from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationReader,
    ProductCollaborationView,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListProductCollaboratorsQuery:
    actor_id: UserID
    product_id: ProductID
    pagination: Pagination


@final
class ListProductCollaboratorsQueryHandler:
    """Lists collaborators (and pending invites) for a product.

    Caller needs ``MANAGE_COLLABORATORS`` — typically owner or
    Moderator. Lower-permission collaborators do not see who else
    is on the team.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: ProductCollaborationReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader

    async def run(
        self,
        data: ListProductCollaboratorsQuery,
    ) -> list[ProductCollaborationView]:
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_COLLABORATORS,
        )
        return await self._reader.for_product(
            data.product_id,
            data.pagination,
        )
