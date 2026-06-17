"""Cluster-wide advisory lock for periodic (cron-driven) jobs.

A single neutral home for :class:`GlobalSchedulerLock`, shared by every
scheduled handler that must single-flight across replicas — storage-quota
reconciliation and the abandoned-unverified-user purge today. It lives
here rather than under any one aggregate's persistence module because it
guards the *scheduler*, not a domain entity: coupling ``auth`` to
``persistence.billing`` just to reach the lock would be misleading.
"""

from typing import Protocol


class GlobalSchedulerLock(Protocol):
    """Cluster-wide non-blocking lock for periodic jobs.

    Hardens cron-driven handlers against multi-replica schedulers:
    if more than one scheduler-pod queues the same tick, every
    worker that picks up a duplicate ``.kiq()`` enters the handler,
    tries to acquire the lock, fails immediately, and exits. Only
    the first worker proceeds. The single-replica scheduler stays
    the recommended deployment; this is the belt to its braces.

    It also guards against a single replica overlapping itself: if a
    pass runs longer than the cron interval (e.g. the 15-minute
    unverified-user purge on a large table), the next tick fails
    ``try_acquire`` and skips rather than piling a second pass on top.

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
