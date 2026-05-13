from dataclasses import dataclass
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileView
from learnic.entities.user.models import User, UserID


@dataclass(slots=True, frozen=True)
class UserView:
    """Read-side projection of :class:`User` returned by the Reader."""

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None
    is_verified: bool
    description: str | None
    avatar: FileView | None
    cover: FileView | None
    website_url: str | None
    portfolio_url: str | None
    public_email: str | None


@dataclass(slots=True, frozen=True)
class UserSummaryView:
    """Lightweight user projection used by name search.

    Excludes ``email`` and ``description`` deliberately — see the
    privacy stance documented on :class:`UserSchema`. The reader still
    resolves the avatar so the caller can display a recognizable
    thumbnail without a follow-up round-trip.
    """

    oid: UserID
    first_name: str
    last_name: str
    patronymic: str | None
    is_verified: bool
    avatar: FileView | None


class UserGateway(Protocol):
    """Write-side lookups for :class:`User`."""

    async def with_id(self, oid: UserID) -> User | None: ...

    async def with_email(self, email: str) -> User | None: ...


class UserReader(Protocol):
    """Read-side queries returning :class:`UserView` projections."""

    async def with_id(self, oid: UserID) -> UserView | None: ...

    async def search_by_name(
        self,
        tokens: tuple[str, ...],
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        """Return users whose name fields match every ``tokens`` entry.

        Each token must match (case-insensitively, as a substring)
        at least one of ``first_name`` / ``last_name`` / ``patronymic``;
        a user is returned only when every token finds a hit. Tokens
        are pre-trimmed and pre-deduplicated by the application layer.

        Implementations are free to add ordering rules — e.g. surface
        prefix matches before substring matches — but must not silently
        widen the result beyond the stated semantics.
        """
        ...
