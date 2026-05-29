"""Persistence contracts for the billing aggregate."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.billing.ids import PlanCode, SubscriptionID
from learnic.entities.billing.models import StorageQuotaBreach, Subscription
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SubscriptionView:
    """Read-side projection of an active subscription.

    Carries only the fields the SPA needs to render a "your tariff"
    card. The plan's display name and limits are NOT here — they live
    in the in-code registry and are joined at the application layer.
    """

    oid: SubscriptionID
    user_id: UserID
    plan_code: PlanCode
    granted_at: datetime
    expires_at: datetime | None


class SubscriptionGateway(Protocol):
    """Write-side lookups for :class:`Subscription`."""

    async def current_for_user(
        self,
        user_id: UserID,
    ) -> Subscription | None:
        """Return the most recent unrevoked, unexpired subscription.

        ``None`` means the user is on the default (FREE) plan.
        """
        ...


class SubscriptionReader(Protocol):
    """Read-side lookups returning view projections."""

    async def current_for_user(
        self,
        user_id: UserID,
    ) -> SubscriptionView | None:
        """Return the active :class:`SubscriptionView` or ``None``."""
        ...


class FileUsageReader(Protocol):
    """Aggregate storage usage attributable to a course author.

    Counts the size of files referenced by ANY of the three
    file-backed block types (file / video-file / photo-collage)
    inside courses authored by ``user_id``. Files referenced from
    multiple blocks are counted once — the underlying storage cost
    is paid once, the quota mirrors that.
    """

    async def bytes_used_by_course_author(self, user_id: UserID) -> int: ...

    async def usage_by_all_authors(self) -> dict[UserID, int]:
        """Return ``{author_id: bytes_used}`` for every author with usage.

        Pre-aggregated in SQL so the reconciliation job avoids
        N+1: it processes every author with at least one
        deduplicated, non-soft-deleted file in their courses in a
        single round-trip. Authors with zero usage are absent from
        the result (no breach is possible for them).
        """
        ...


@dataclass(slots=True, frozen=True)
class AuthorFileRef:
    """Pointer to one of an author's live files for the LIFO picker.

    The reconciliation job soft-deletes by walking these in
    ``uploaded_at DESC`` order and updating ``file.mark_deleted()``
    until ``used <= limit``. Only ``oid`` + ``size_bytes`` are needed
    — name, content type, etc. are irrelevant to the eviction
    decision.
    """

    file_id: FileID
    size_bytes: int


class StorageQuotaBreachGateway(Protocol):
    """Write-side lookups + persistence for :class:`StorageQuotaBreach`."""

    async def with_user(
        self,
        user_id: UserID,
    ) -> StorageQuotaBreach | None:
        """Return the open breach for ``user_id`` or ``None``.

        At most one open breach per user (enforced via UNIQUE on
        ``user_id``); a present row means the user is currently over
        quota and the grace timer is running.
        """
        ...

    async def all_open(self) -> list[StorageQuotaBreach]:
        """Return every currently-open breach.

        Used by the reconciliation job to double-check users who
        cleared their overage on their own — a user whose breach
        record exists but who no longer over-uses storage gets the
        record dropped this scan.
        """
        ...

    async def delete(self, breach: StorageQuotaBreach) -> None: ...


class AuthorActiveFilesReader(Protocol):
    """Read-side projection of an author's live files for LIFO eviction.

    Returns files referenced from courses authored by ``user_id``,
    ordered by ``uploaded_at`` descending (newest first), filtered
    to ``deleted_at IS NULL``. The reconciliation job walks the
    iterator until ``cumulative_size >= over_bytes`` and stops —
    no need to load the full list for owners with thousands of
    files.
    """

    async def newest_first(
        self,
        user_id: UserID,
    ) -> list[AuthorFileRef]: ...


class GlobalSchedulerLock(Protocol):
    """Cluster-wide non-blocking lock for periodic jobs.

    Hardens cron-driven handlers against multi-replica schedulers:
    if more than one scheduler-pod queues the same tick, every
    worker that picks up a duplicate ``.kiq()`` enters the handler,
    tries to acquire the lock, fails immediately, and exits. Only
    the first worker proceeds. The single-replica scheduler stays
    the recommended deployment; this is the belt to its braces.

    Implementations use a Postgres **session-level** advisory lock
    (``pg_try_advisory_lock`` / ``pg_advisory_unlock``) rather than
    a transaction-scoped one because handlers like
    :class:`ReconcileStorageQuotasCommandHandler` commit several
    times inside one run — a xact-lock would release on the first
    commit and leave the rest of the pass unprotected. The lock is
    held on a dedicated connection for the whole acquire→release
    window (NOT the request session, whose connection returns to the
    pool on every commit and would strand the lock), and is freed
    automatically if that connection drops (worker crash), so a
    crashed worker never holds the lock forever.
    """

    async def try_acquire(self, key: str) -> bool:
        """Acquire the lock keyed on ``key``.

        Returns ``True`` if the caller now holds the lock,
        ``False`` if another session is already holding it (no
        wait). The caller MUST pair every ``True`` return with a
        ``release(key)`` in a ``finally``.
        """
        ...

    async def release(self, key: str) -> None: ...


class StorageQuotaLock(Protocol):
    """Per-user serialization point for quota-changing operations.

    Implementations take a transaction-scoped lock keyed on the
    quota-owning user; concurrent uploads against the same owner
    block here until the holding transaction commits or rolls back.
    Cross-owner traffic is unaffected. The lock is auto-released
    on transaction end — callers do not unlock by hand.

    The contract is "the next read of the owner's storage usage
    inside this transaction reflects every committed prior upload",
    which is what closes the TOCTOU window between the quota check
    and the file-row insert.
    """

    async def acquire_for(self, quota_owner_id: UserID) -> None: ...
