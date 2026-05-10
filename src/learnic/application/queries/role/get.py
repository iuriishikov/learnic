from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.persistence.role import (
    RoleReader,
    RoleView,
)
from learnic.application.common.validators import validate_empty
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetRoleQuery:
    actor_id: UserID
    role_id: RoleID


@final
class GetRoleQueryHandler:
    def __init__(
        self,
        authorizer: Authorizer,
        reader: RoleReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader

    async def run(self, data: GetRoleQuery) -> RoleView:
        view = validate_empty(
            await self._reader.with_id(data.role_id),
            data.role_id,
        )
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(view.product_id),
            Permission.READ_PRODUCT,
        )
        return view
