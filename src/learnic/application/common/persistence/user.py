from dataclasses import dataclass
from typing import Protocol

from learnic.entities.user.models import User, UserID


@dataclass(slots=True, frozen=True)
class UserView:
    """Read-side projection of :class:`User` returned by the Reader."""

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None


class UserGateway(Protocol):
    """Write-side lookups for :class:`User`."""

    async def with_id(self, oid: UserID) -> User | None: ...

    async def with_email(self, email: str) -> User | None: ...


class UserReader(Protocol):
    """Read-side queries returning :class:`UserView` projections."""

    async def with_id(self, oid: UserID) -> UserView | None: ...
