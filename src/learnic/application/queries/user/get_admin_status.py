from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.user import UserReader
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyAdminStatusQuery:
    user_id: UserID


@dataclass(slots=True, frozen=True)
class AdminStatusView:
    is_admin: bool


@final
class GetMyAdminStatusQueryHandler:
    """Report whether the caller is a platform administrator.

    Backs the authenticated ``GET /users/me/admin-status`` endpoint so
    the SPA can gate admin-only UI. Deliberately a caller-scoped read
    (not behind the admin gate) — a non-admin must be able to learn
    they are *not* an admin instead of getting a 403.
    """

    def __init__(self, user_reader: UserReader) -> None:
        self._user_reader: Final = user_reader

    async def run(self, data: GetMyAdminStatusQuery) -> AdminStatusView:
        is_admin = await self._user_reader.is_admin(data.user_id)
        if is_admin is None:
            raise EntityNotFoundError(data.user_id)
        return AdminStatusView(is_admin=is_admin)
