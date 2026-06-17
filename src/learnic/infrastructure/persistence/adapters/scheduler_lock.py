"""Postgres advisory-lock implementation of :class:`GlobalSchedulerLock`.

Lives in its own adapter module (not under ``adapters/billing``) because
the lock is aggregate-agnostic — it is shared by the storage-quota
reconcile and the unverified-user purge, and more periodic jobs later.
"""

from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from typing_extensions import override

from learnic.application.common.persistence.scheduler_lock import (
    GlobalSchedulerLock,
)


class GlobalSchedulerLockAlchemy(GlobalSchedulerLock):
    """Postgres session-level advisory lock on a dedicated connection.

    A session-level ``pg_advisory_lock`` is tied to the Postgres
    backend connection, not to a transaction, so it survives the
    several intermediate commits a scheduled handler performs. The
    catch: the handler's request-scoped ``AsyncSession`` returns its
    connection to the pool on every ``commit()``, so running the lock
    through that session would strand it on a pooled connection and
    fire the final ``pg_advisory_unlock`` on a different one — the
    lock would leak and the next run could skip forever. So this
    adapter checks out its OWN ``AsyncConnection`` and holds it for
    the whole acquire→release window, independent of the job's
    session. A ``commit()`` after each statement keeps the connection
    out of "idle in transaction"; the session-level lock persists
    regardless. If the worker crashes, the connection drops and
    Postgres frees the lock automatically.

    Key string is hashed to a stable 64-bit integer via
    ``hashtextextended`` so callers use human-readable identifiers
    (``"storage_quota_reconcile"``) without picking bigint magic
    numbers.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine: Final = engine
        self._conn: AsyncConnection | None = None

    @override
    async def try_acquire(self, key: str) -> bool:
        conn = await self._engine.connect()
        result = await conn.execute(
            sa.text("SELECT pg_try_advisory_lock(hashtextextended(:k, 0))"),
            {"k": key},
        )
        await conn.commit()
        if not bool(result.scalar()):
            await conn.close()
            return False
        self._conn = conn
        return True

    @override
    async def release(self, key: str) -> None:
        conn = self._conn
        if conn is None:
            return
        self._conn = None
        try:
            await conn.execute(
                sa.text(
                    "SELECT pg_advisory_unlock(hashtextextended(:k, 0))",
                ),
                {"k": key},
            )
            await conn.commit()
        finally:
            await conn.close()
