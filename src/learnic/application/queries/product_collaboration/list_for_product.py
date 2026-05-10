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

    Caller needs ``READ_PRODUCT`` — any collaborator can see who
    else is on the team, but only those with
    ``MANAGE_COLLABORATORS`` may invite or revoke (enforced on the
    write commands). The team list is part of the product's
    overview, not a privileged view.
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
            Permission.READ_PRODUCT,
        )
        return await self._reader.for_product(
            data.product_id,
            data.pagination,
        )
