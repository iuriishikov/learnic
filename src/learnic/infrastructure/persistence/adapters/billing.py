"""Alchemy adapters for the billing aggregate.

Three concrete adapters:

* ``SubscriptionMapperAlchemy`` — write-side lookup returning
  :class:`Subscription` entities.
* ``SubscriptionReaderAlchemy`` — read-side lookup returning
  :class:`SubscriptionView` projections.
* ``FileUsageReaderAlchemy`` — aggregates ``files.size_bytes``
  across the three file-backed block types referenced from a given
  author's notes.
"""

from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
)
from typing_extensions import override

from learnic.application.common.persistence.billing import (
    AuthorActiveFilesReader,
    AuthorFileRef,
    FileUsageReader,
    GlobalSchedulerLock,
    StorageQuotaBreachGateway,
    StorageQuotaLock,
    SubscriptionGateway,
    SubscriptionReader,
    SubscriptionView,
)
from learnic.entities.billing.ids import PlanCode, SubscriptionID
from learnic.entities.billing.models import StorageQuotaBreach, Subscription
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.note_block import (
    file_blocks_table,
    lesson_blocks_table,
    photo_collage_items_table,
    video_file_blocks_table,
)
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.subscription import (
    storage_quota_breaches_table,
    subscriptions_table,
)


def _current_subscription_stmt(user_id: UserID) -> sa.Select[Any]:
    """SELECT for the most recent currently-active subscription.

    Filters ``revoked_at IS NULL`` and ``expires_at`` either NULL or
    strictly in the future; orders by ``granted_at`` desc to pick the
    latest grant when (rare) multiple actives overlap.
    """
    return (
        sa.select(subscriptions_table)
        .where(
            subscriptions_table.c.user_id == user_id,
            subscriptions_table.c.revoked_at.is_(None),
            sa.or_(
                subscriptions_table.c.expires_at.is_(None),
                subscriptions_table.c.expires_at > sa.func.now(),
            ),
        )
        .order_by(subscriptions_table.c.granted_at.desc())
        .limit(1)
    )


class SubscriptionMapperAlchemy(SubscriptionGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def current_for_user(
        self,
        user_id: UserID,
    ) -> Subscription | None:
        stmt = sa.select(Subscription).where(
            subscriptions_table.c.user_id == user_id,
            subscriptions_table.c.revoked_at.is_(None),
            sa.or_(
                subscriptions_table.c.expires_at.is_(None),
                subscriptions_table.c.expires_at > sa.func.now(),
            ),
        ).order_by(subscriptions_table.c.granted_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class SubscriptionReaderAlchemy(SubscriptionReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def current_for_user(
        self,
        user_id: UserID,
    ) -> SubscriptionView | None:
        stmt = _current_subscription_stmt(user_id)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return SubscriptionView(
            oid=SubscriptionID(row.oid),
            user_id=UserID(row.user_id),
            plan_code=PlanCode(row.plan_code),
            granted_at=row.granted_at,
            expires_at=row.expires_at,
        )


class FileUsageReaderAlchemy(FileUsageReader):
    """Sums ``files.size_bytes`` for files referenced from author's blocks.

    Joins through three pathways (one per file-backed block type) and
    deduplicates via the outer ``DISTINCT files.oid`` — a file
    referenced from multiple blocks (e.g. same image in two collages)
    is paid for once. Soft-deleted files are excluded via the
    ``files.deleted_at IS NULL`` predicate.

    Collage items live in their own ``photo_collage_items`` table
    (one row per photo), so the collage path is a straight join —
    no JSONB expansion needed.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def bytes_used_by_note_author(self, user_id: UserID) -> int:
        # File-block path: file_id is a direct column on file_blocks.
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        # Video-file path: same shape, different table.
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        # Collage path: items now live in a child table, so it's a
        # straight join — `photo_collage_items.block_id` lines up with
        # `lesson_blocks.oid` via the photo-collage subtype's PK.
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        referenced_file_ids = sa.union_all(
            file_path,
            video_path,
            collage_path,
        ).subquery("referenced_file_ids")
        stmt = sa.select(
            sa.func.coalesce(sa.func.sum(files_table.c.size_bytes), 0),
        ).where(
            files_table.c.deleted_at.is_(None),
            files_table.c.oid.in_(
                sa.select(referenced_file_ids.c.file_id).distinct(),
            ),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @override
    async def bytes_used_by_product(self, product_id: ProductID) -> int:
        # Same three-path union as bytes_used_by_note_author, scoped
        # to one product — lesson_blocks carries product_id directly,
        # so no products join is needed.
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ),
            )
            .where(
                lesson_blocks_table.c.product_id == product_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        referenced_file_ids = sa.union_all(
            file_path,
            video_path,
            collage_path,
        ).subquery("product_referenced_file_ids")
        stmt = sa.select(
            sa.func.coalesce(sa.func.sum(files_table.c.size_bytes), 0),
        ).where(
            files_table.c.deleted_at.is_(None),
            files_table.c.oid.in_(
                sa.select(referenced_file_ids.c.file_id).distinct(),
            ),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @override
    async def usage_by_all_authors(self) -> dict[UserID, int]:
        # Same three-path union as bytes_used_by_note_author, but
        # carrying author_id alongside the file_id so we can GROUP BY
        # author after DISTINCT-deduplicating files.
        file_path = (
            sa.select(
                products_table.c.author_id.label("author_id"),
                file_blocks_table.c.file_id.label("file_id"),
            )
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(file_blocks_table.c.file_id.is_not(None))
        )
        video_path = (
            sa.select(
                products_table.c.author_id.label("author_id"),
                video_file_blocks_table.c.file_id.label("file_id"),
            )
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(video_file_blocks_table.c.file_id.is_not(None))
        )
        collage_path = (
            sa.select(
                products_table.c.author_id.label("author_id"),
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(photo_collage_items_table.c.file_id.is_not(None))
        )
        per_author_file = (
            sa.union_all(file_path, video_path, collage_path)
            .subquery("per_author_file")
        )
        dedup = sa.select(
            per_author_file.c.author_id,
            per_author_file.c.file_id,
        ).distinct().subquery("dedup")
        stmt = (
            sa.select(
                dedup.c.author_id,
                sa.func.sum(files_table.c.size_bytes).label("total"),
            )
            .select_from(
                dedup.join(
                    files_table,
                    files_table.c.oid == dedup.c.file_id,
                ),
            )
            .where(files_table.c.deleted_at.is_(None))
            .group_by(dedup.c.author_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {UserID(row.author_id): int(row.total) for row in rows}


class StorageQuotaBreachMapperAlchemy(StorageQuotaBreachGateway):
    """Read / mutate :class:`StorageQuotaBreach` rows.

    The row is keyed on ``user_id UNIQUE`` so ``with_user`` resolves
    a single open breach without further filters. ``all_open`` is a
    full scan — the table stays small (one row per currently-
    over-quota user) so this is cheap; the reconciliation job is
    the only caller and runs on a slow cadence anyway.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_user(
        self,
        user_id: UserID,
    ) -> StorageQuotaBreach | None:
        stmt = sa.select(StorageQuotaBreach).where(
            storage_quota_breaches_table.c.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def all_open(self) -> list[StorageQuotaBreach]:
        stmt = sa.select(StorageQuotaBreach)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, breach: StorageQuotaBreach) -> None:
        await self._session.delete(breach)


class AuthorActiveFilesReaderAlchemy(AuthorActiveFilesReader):
    """Walk an author's live files newest-first via note-block joins.

    Mirrors :class:`FileUsageReaderAlchemy`'s scoping (files
    referenced by file / video-file / photo-collage blocks within
    notes authored by ``user_id``, deduplicated via DISTINCT,
    soft-deleted excluded) but emits per-file rows ordered by
    ``files.uploaded_at DESC`` for LIFO eviction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def newest_first(
        self,
        user_id: UserID,
    ) -> list[AuthorFileRef]:
        file_path = (
            sa.select(file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                file_blocks_table.c.file_id.is_not(None),
            )
        )
        video_path = (
            sa.select(video_file_blocks_table.c.file_id.label("file_id"))
            .select_from(
                video_file_blocks_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == video_file_blocks_table.c.oid,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                video_file_blocks_table.c.file_id.is_not(None),
            )
        )
        collage_path = (
            sa.select(
                photo_collage_items_table.c.file_id.label("file_id"),
            )
            .select_from(
                photo_collage_items_table.join(
                    lesson_blocks_table,
                    lesson_blocks_table.c.oid
                    == photo_collage_items_table.c.block_id,
                ).join(
                    products_table,
                    products_table.c.oid == lesson_blocks_table.c.product_id,
                ),
            )
            .where(
                products_table.c.author_id == user_id,
                photo_collage_items_table.c.file_id.is_not(None),
            )
        )
        referenced_file_ids = sa.union_all(
            file_path,
            video_path,
            collage_path,
        ).subquery("referenced_file_ids")
        stmt = (
            sa.select(
                files_table.c.oid,
                files_table.c.size_bytes,
            )
            .where(
                files_table.c.deleted_at.is_(None),
                files_table.c.oid.in_(
                    sa.select(referenced_file_ids.c.file_id).distinct(),
                ),
            )
            .order_by(files_table.c.uploaded_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            AuthorFileRef(
                file_id=FileID(row.oid),
                size_bytes=int(row.size_bytes),
            )
            for row in rows
        ]


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


class StorageQuotaLockAlchemy(StorageQuotaLock):
    """Postgres ``pg_advisory_xact_lock`` keyed on the owner UUID.

    Serializes quota-changing operations per quota owner inside the
    current transaction. The 64-bit lock key is derived from the
    UUID via ``hashtextextended`` (zero seed) — collisions across
    different owners are astronomically rare and degrade only into
    benign extra serialization, never into a correctness problem.
    Released automatically on COMMIT / ROLLBACK; nothing to clean up.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def acquire_for(self, quota_owner_id: UserID) -> None:
        await self._session.execute(
            sa.text(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended(:k, 0))",
            ),
            {"k": str(quota_owner_id)},
        )
