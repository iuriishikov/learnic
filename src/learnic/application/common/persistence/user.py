from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
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
    avatar: FileMeta | None
    cover: FileMeta | None
    website_url: str | None
    portfolio_url: str | None
    public_email: str | None


@dataclass(slots=True, frozen=True)
class UserSummaryView:
    """Lightweight user projection used by name search and admin list.

    Carries the user's raw login ``email`` so the query handler can
    mask it before it leaves the application layer; ``description``
    stays out as it is not part of this projection. The reader also
    resolves the avatar so the caller can display a recognizable
    thumbnail without a follow-up round-trip.
    """

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None
    is_verified: bool
    is_banned: bool
    avatar: FileMeta | None


class UserGateway(Protocol):
    """Write-side lookups for :class:`User`."""

    async def with_id(self, oid: UserID) -> User | None: ...

    async def with_email(self, email: str) -> User | None: ...

    async def delete_abandoned_unverified(self, now: datetime) -> int:
        """Bulk-delete unverified accounts past self-recovery.

        Targets exactly the rows that can no longer self-verify:
        ``email_verified`` is false, there is no active VERIFY email
        token, and no active signup session (both judged against
        ``now``). Such a row is a permanent squatter — login is
        blocked, resend needs the gone signup session, and the UNIQUE
        ``email`` blocks re-registration — so removing it frees the
        address and stops indefinite accumulation. Returns the number
        of rows deleted (zero on a no-op pass).
        """
        ...


class UserReader(Protocol):
    """Read-side queries returning :class:`UserView` projections."""

    async def with_id(self, oid: UserID) -> UserView | None: ...

    async def is_admin(self, oid: UserID) -> bool | None:
        """Return the user's platform-admin flag, or ``None`` if absent.

        ``None`` distinguishes "no such user" from a real ``False`` so
        the caller can map a vanished account to a 404 rather than
        silently reporting "not an admin".
        """
        ...

    async def admins(
        self,
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        """Return the platform's administrator accounts.

        Only non-banned users carrying the ``is_admin`` flag are
        included, ordered by ``last_name`` / ``first_name`` / ``oid``
        ascending for a stable, deterministic page across requests.
        """
        ...

    async def search_by_name(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        """Return users matching ``query`` across their name fields.

        Full-text + fuzzy search (mirrors the product catalog search):
        ``search_vector @@ websearch_to_tsquery('russian', q)`` OR a
        trigram ``word_similarity`` fallback over the concatenated
        name text, ranked by a weighted blend of the two and tie-broken
        by ``last_name`` / ``first_name`` / ``oid`` for stable
        pagination. ``query`` arrives pre-trimmed; an empty string must
        return an empty list without touching the index.
        """
        ...
