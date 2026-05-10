from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.persistence.role import (
    RoleReader,
    RoleView,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListProductRolesQuery:
    actor_id: UserID
    product_id: ProductID


@final
class ListProductRolesQueryHandler:
    """Return roles defined inside a product.

    Caller needs ``READ_PRODUCT`` on the target product, so only
    collaborators (and the owner) can introspect role definitions.
    Returns an empty list while the product has no roles yet — the
    Team-tab onboarding flow on the SPA reacts to that signal to
    prompt the author to create an initial set.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: RoleReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader

    async def run(
        self,
        data: ListProductRolesQuery,
    ) -> list[RoleView]:
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        return await self._reader.for_product(data.product_id)
