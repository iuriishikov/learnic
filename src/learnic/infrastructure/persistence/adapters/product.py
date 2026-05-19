from datetime import timedelta
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.product import (
    ProductGateway,
    ProductReader,
    ProductView,
    RecommendationCandidate,
)
from learnic.application.common.persistence.tag import TagView
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product_collaboration.enums import (
    CollaborationStatus,
)
from learnic.entities.tag.ids import TagID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.enrollment import (
    enrollments_table,
)
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.product import (
    products_table,
)
from learnic.infrastructure.persistence.models.product_collaboration import (
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.tag import (
    product_tags_table,
    tags_table,
)
from learnic.infrastructure.persistence.models.user import users_table


class ProductMapperAlchemy(ProductGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: ProductID) -> Product | None:
        stmt = sa.select(Product).where(products_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def delete(self, product: Product) -> None:
        await self._session.delete(product)


def _row_to_view(
    row: sa.Row[Any],
    tags: list[TagView],
) -> ProductView:
    return ProductView(
        oid=ProductID(row.oid),
        type=row.type,
        status=row.status,
        name=row.name,
        description=row.description,
        total_duration_in_hours=row.total_duration_in_hours,
        author=UserRefView(
            oid=UserID(row.author_oid),
            email=row.author_email,
            first_name=row.author_first_name,
            last_name=row.author_last_name,
            patronymic=row.author_patronymic,
        ),
        cover=(
            FileMeta(
                oid=FileID(row.cover_oid),
                storage_name=row.cover_storage_name,
                bucket=row.cover_bucket,
                content_type=row.cover_content_type,
                size_bytes=row.cover_size_bytes,
            )
            if row.cover_oid is not None
            else None
        ),
        tags=tags,
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _select_with_joins() -> sa.Select[Any]:
    cover = files_table.alias("cover")
    return sa.select(
        products_table.c.oid,
        products_table.c.type,
        products_table.c.status,
        products_table.c.name,
        products_table.c.description,
        products_table.c.total_duration_in_hours,
        products_table.c.published_at,
        products_table.c.created_at,
        products_table.c.updated_at,
        cover.c.oid.label("cover_oid"),
        cover.c.storage_name.label("cover_storage_name"),
        cover.c.bucket.label("cover_bucket"),
        cover.c.content_type.label("cover_content_type"),
        cover.c.size_bytes.label("cover_size_bytes"),
        users_table.c.oid.label("author_oid"),
        users_table.c.email.label("author_email"),
        users_table.c.first_name.label("author_first_name"),
        users_table.c.last_name.label("author_last_name"),
        users_table.c.patronymic.label("author_patronymic"),
    ).select_from(
        products_table.join(
            users_table,
            products_table.c.author_id == users_table.c.oid,
        )
        .outerjoin(
            cover,
            sa.and_(
                products_table.c.cover_file_id == cover.c.oid,
                cover.c.deleted_at.is_(None),
            ),
        ),
    )


class ProductReaderAlchemy(ProductReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    async def _tags_by_product(
        self,
        product_ids: list[ProductID],
    ) -> dict[ProductID, list[TagView]]:
        """Batch-fetch the ``product_tags`` slice for every product.

        One SQL round-trip (``IN`` query + JOIN onto ``tags``)
        regardless of how many products the caller is listing —
        callers (`accessible_to`, `published`, `search_published`,
        `published_by_author`, `recommendation_candidates`, …) avoid
        the N+1 they would hit if each row queried tags on its own.

        Ordering preserves ``product_tags.position`` per product so
        author-defined order survives end-to-end.
        """
        if not product_ids:
            return {}
        stmt = (
            sa.select(
                product_tags_table.c.product_id,
                tags_table.c.oid,
                tags_table.c.name,
                tags_table.c.color,
            )
            .select_from(
                product_tags_table.join(
                    tags_table,
                    product_tags_table.c.tag_id == tags_table.c.oid,
                ),
            )
            .where(product_tags_table.c.product_id.in_(product_ids))
            .order_by(
                product_tags_table.c.product_id.asc(),
                product_tags_table.c.position.asc(),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        result: dict[ProductID, list[TagView]] = {}
        for row in rows:
            result.setdefault(ProductID(row.product_id), []).append(
                TagView(
                    oid=TagID(row.oid),
                    name=row.name,
                    color=row.color,
                ),
            )
        return result

    async def _rows_to_views(
        self,
        rows: list[sa.Row[Any]],
    ) -> list[ProductView]:
        tags_by_id = await self._tags_by_product(
            [ProductID(r.oid) for r in rows],
        )
        return [
            _row_to_view(r, tags_by_id.get(ProductID(r.oid), []))
            for r in rows
        ]

    @override
    async def with_id(self, oid: ProductID) -> ProductView | None:
        stmt = _select_with_joins().where(products_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        tags_by_id = await self._tags_by_product([ProductID(row.oid)])
        return _row_to_view(row, tags_by_id.get(ProductID(row.oid), []))

    @override
    async def accessible_to(
        self,
        user_id: UserID,
        pagination: Pagination,
    ) -> list[ProductView]:
        active_collab_product_ids = sa.select(
            product_collaborations_table.c.product_id,
        ).where(
            product_collaborations_table.c.collaborator_id == user_id,
            product_collaborations_table.c.status == CollaborationStatus.ACTIVE.value,
        )
        stmt = (
            _select_with_joins()
            .where(
                sa.or_(
                    products_table.c.author_id == user_id,
                    products_table.c.oid.in_(active_collab_product_ids),
                ),
            )
            # ``oid`` tie-breaker keeps pagination stable when many
            # rows share the same ``created_at`` (bulk imports,
            # seed scripts, multi-row INSERTs — all stamp the same
            # transaction-time ``now()``). Without it, offset/limit
            # can return the same row on consecutive pages and
            # cause React duplicate-key warnings on the client.
            .order_by(
                products_table.c.created_at.desc(),
                products_table.c.oid.desc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = list((await self._session.execute(stmt)).all())
        return await self._rows_to_views(rows)

    @override
    async def published(
        self,
        pagination: Pagination,
    ) -> list[ProductView]:
        stmt = (
            _select_with_joins()
            .where(products_table.c.status == ProductStatus.PUBLISHED.value)
            # See ``accessible_to`` for why ``oid`` is a secondary
            # ORDER BY — keeps offset pagination stable across
            # rows with identical ``created_at``.
            .order_by(
                products_table.c.created_at.desc(),
                products_table.c.oid.desc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = list((await self._session.execute(stmt)).all())
        return await self._rows_to_views(rows)

    @override
    async def published_count(self) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(products_table)
            .where(
                products_table.c.status == ProductStatus.PUBLISHED.value,
            )
        )
        return (await self._session.scalar(stmt)) or 0

    async def _prepare_search_predicates(
        self,
        query: str,
    ) -> tuple[
        str,
        sa.Function[sa.sql.elements.ColumnElement[object]],
        sa.ColumnElement[bool],
    ]:
        """Lower-case the query, lock the trigram threshold, build
        the shared tsquery + WHERE predicate used by both
        ``search_published`` and ``search_published_count``.

        Returns ``(query_lower, tsq, predicate)``. ``predicate`` is
        ``status=published AND (tsv @@ tsq OR text %> query_lower)``.
        Side effect: issues ``SET LOCAL
        pg_trgm.word_similarity_threshold = 0.4`` against the
        current session — both callers must run inside the same
        transaction as their follow-up query.
        """
        # `search_text` is stored already lower-cased by the trigger,
        # so we lower the incoming query too — trigram operators
        # are case-sensitive. tsvector matching is dictionary-driven
        # and case-insensitive regardless.
        query_lower = query.strip().lower()
        # Default ``word_similarity_threshold = 0.6`` is too strict
        # for product search — one extra character past a typo
        # collapses the score below the cutoff. 0.4 still rejects
        # noise (random short queries) while catching realistic
        # 1–2 char typos / inflections that the russian tsvector
        # dictionary missed. ``SET LOCAL`` scopes the change to
        # this transaction only.
        await self._session.execute(
            sa.text(
                "SET LOCAL pg_trgm.word_similarity_threshold = 0.4",
            ),
        )
        # `websearch_to_tsquery` accepts user-friendly syntax
        # (quoted phrases, `OR`, leading `-`) without raising on
        # parse errors — safer than `plainto_tsquery` for arbitrary
        # input.
        #
        # The first argument must be ``regconfig``. In raw psql
        # ``'russian'`` auto-coerces from the ``unknown`` literal
        # type; over asyncpg's prepared-statement protocol every
        # parameter is sent as ``$N::VARCHAR``, which does not
        # coerce, so Postgres raises ``UndefinedFunctionError``.
        # ``literal_column`` injects the cast verbatim into the
        # rendered SQL — Postgres sees ``'russian'::regconfig``
        # and picks the right overload.
        russian_regconfig: sa.ColumnElement[str] = sa.literal_column(
            "'russian'::regconfig",
        )
        tsq = sa.func.websearch_to_tsquery(
            russian_regconfig, query_lower,
        )
        predicate = sa.and_(
            products_table.c.status == ProductStatus.PUBLISHED.value,
            sa.or_(
                products_table.c.search_vector.op("@@")(tsq),
                # ``search_text %> query`` ≡
                # ``word_similarity(query, search_text) >
                # pg_trgm.word_similarity_threshold`` (default
                # 0.6). Indexed by the GIN ``gin_trgm_ops``
                # index when the indexed column is on the
                # left of ``%>``.
                products_table.c.search_text.op("%>")(query_lower),
            ),
        )
        return query_lower, tsq, predicate

    @override
    async def search_published(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[ProductView]:
        query_lower, tsq, predicate = await (
            self._prepare_search_predicates(query)
        )
        rank_ts = sa.func.ts_rank_cd(
            products_table.c.search_vector, tsq,
        ).label("rank_ts")
        # `word_similarity(query, haystack)` finds the best-matching
        # word substring inside ``search_text`` and scores against
        # it — the right operator for short-query-vs-long-document.
        # Plain ``similarity()`` would divide matched trigrams by
        # the haystack's total trigram count and collapse scores
        # to ~0 on long concatenated text.
        rank_trgm = sa.func.word_similarity(
            query_lower, products_table.c.search_text,
        ).label("rank_trgm")
        stmt = (
            _select_with_joins()
            .add_columns(rank_ts, rank_trgm)
            .where(predicate)
            # tsvector (morphology + weights) carries twice the
            # weight of trigram (typos/transliteration) — exact /
            # near-exact word matches dominate, fuzziness fills
            # gaps. Tie-break by recency, then by ``oid`` so
            # pagination stays stable across rows with identical
            # rank AND identical ``created_at`` (bulk imports).
            .order_by(
                (
                    rank_ts * sa.literal(2.0) + rank_trgm
                ).desc(),
                products_table.c.created_at.desc(),
                products_table.c.oid.desc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = list((await self._session.execute(stmt)).all())
        return await self._rows_to_views(rows)

    @override
    async def search_published_count(self, query: str) -> int:
        # Reuses the exact same WHERE predicate as
        # ``search_published`` (built via the shared
        # ``_prepare_search_predicates`` helper) so the count
        # always matches what the paginated list returns. The
        # tsquery + threshold setup live in the same transaction.
        _query_lower, _tsq, predicate = await (
            self._prepare_search_predicates(query)
        )
        stmt = (
            sa.select(sa.func.count())
            .select_from(products_table)
            .where(predicate)
        )
        return (await self._session.scalar(stmt)) or 0

    @override
    async def published_by_author(
        self,
        author_id: UserID,
        pagination: Pagination,
    ) -> list[ProductView]:
        stmt = (
            _select_with_joins()
            .where(
                products_table.c.author_id == author_id,
                products_table.c.status == ProductStatus.PUBLISHED.value,
            )
            # See ``accessible_to`` for the ``oid`` tie-breaker
            # rationale (stable pagination across identical
            # ``created_at`` rows).
            .order_by(
                products_table.c.created_at.desc(),
                products_table.c.oid.desc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = list((await self._session.execute(stmt)).all())
        return await self._rows_to_views(rows)

    @override
    async def name_exists(
        self,
        author_id: UserID,
        name: str,
        exclude_oid: ProductID | None = None,
    ) -> bool:
        stmt = sa.select(products_table.c.oid).where(
            products_table.c.author_id == author_id,
            products_table.c.name == name,
        )
        if exclude_oid is not None:
            stmt = stmt.where(products_table.c.oid != exclude_oid)
        result = await self._session.execute(stmt.limit(1))
        return result.first() is not None

    @override
    async def recommendation_candidates(
        self,
        user_id: UserID,
        limit: int,
        popularity_window_days: int,
    ) -> list[RecommendationCandidate]:
        # Cutoff for the popularity signal; computed in Python so the
        # SQL plan is stable and we avoid a server-side ``NOW() -
        # INTERVAL`` recompute on every row.
        popularity_since = sa.func.now() - sa.cast(
            sa.literal(timedelta(days=popularity_window_days)),
            sa.Interval,
        )
        active_statuses = (EnrollmentStatus.ACTIVE.value,)

        # --- unified enrollments + product_id ------------------------ #
        # ``product_id`` lives on the parent enrollments row now, so
        # no subtype-table join is required.
        all_enrollments = sa.select(
            enrollments_table.c.student_id.label("student_id"),
            enrollments_table.c.product_id.label("product_id"),
            enrollments_table.c.status.label("status"),
            enrollments_table.c.enrolled_at.label("enrolled_at"),
        ).cte("all_enrollments")

        # --- user profile CTEs --------------------------------------- #
        user_active_products = (
            sa.select(
                all_enrollments.c.product_id.label("product_id"),
            )
            .where(
                all_enrollments.c.student_id == user_id,
                all_enrollments.c.status.in_(active_statuses),
            )
            .distinct()
            .cte("user_active_products")
        )

        # Tags the user has engaged with, weighted by repetition.
        user_tag_profile = (
            sa.select(
                product_tags_table.c.tag_id.label("tag_id"),
                sa.func.count().label("weight"),
            )
            .select_from(
                user_active_products.join(
                    product_tags_table,
                    product_tags_table.c.product_id
                    == user_active_products.c.product_id,
                ),
            )
            .group_by(product_tags_table.c.tag_id)
            .cte("user_tag_profile")
        )

        # Authors the user has bought from, weighted by # of products.
        user_author_profile = (
            sa.select(
                products_table.c.author_id.label("author_id"),
                sa.func.count().label("weight"),
            )
            .select_from(
                user_active_products.join(
                    products_table,
                    products_table.c.oid
                    == user_active_products.c.product_id,
                ),
            )
            .group_by(products_table.c.author_id)
            .cte("user_author_profile")
        )

        # --- exclusion set ------------------------------------------- #
        # Own products + currently-enrolled (REFUNDED is allowed back).
        own_products = sa.select(products_table.c.oid).where(
            products_table.c.author_id == user_id,
        )
        enrolled_products = sa.select(
            user_active_products.c.product_id,
        )
        excluded_products = own_products.union(enrolled_products).cte(
            "excluded_products",
        )

        # --- per-signal candidate CTEs ------------------------------- #
        tag_candidates = (
            sa.select(
                product_tags_table.c.product_id.label("product_id"),
                sa.cast(
                    sa.func.sum(user_tag_profile.c.weight),
                    sa.Float,
                ).label("tag_affinity_raw"),
            )
            .select_from(
                product_tags_table.join(
                    user_tag_profile,
                    user_tag_profile.c.tag_id == product_tags_table.c.tag_id,
                ),
            )
            .group_by(product_tags_table.c.product_id)
            .cte("tag_candidates")
        )

        author_candidates = (
            sa.select(
                products_table.c.oid.label("product_id"),
                sa.cast(
                    sa.func.sum(user_author_profile.c.weight),
                    sa.Float,
                ).label("author_affinity_raw"),
            )
            .select_from(
                products_table.join(
                    user_author_profile,
                    user_author_profile.c.author_id
                    == products_table.c.author_id,
                ),
            )
            .group_by(products_table.c.oid)
            .cte("author_candidates")
        )

        popular_candidates = (
            sa.select(
                all_enrollments.c.product_id.label("product_id"),
                sa.cast(
                    sa.func.count(
                        sa.distinct(all_enrollments.c.student_id),
                    ),
                    sa.Float,
                ).label("popularity_raw"),
            )
            .where(
                all_enrollments.c.enrolled_at > popularity_since,
                all_enrollments.c.status.in_(active_statuses),
            )
            .group_by(all_enrollments.c.product_id)
            .cte("popular_candidates")
        )

        # --- union of candidate ids ---------------------------------- #
        candidate_ids = (
            sa.select(tag_candidates.c.product_id)
            .union(
                sa.select(author_candidates.c.product_id),
                sa.select(popular_candidates.c.product_id),
            )
            .cte("candidate_ids")
        )

        # --- final select: base view + raw signals ------------------- #
        tag_raw = sa.func.coalesce(
            tag_candidates.c.tag_affinity_raw, 0.0,
        ).label("tag_affinity_raw")
        author_raw = sa.func.coalesce(
            author_candidates.c.author_affinity_raw, 0.0,
        ).label("author_affinity_raw")
        pop_raw = sa.func.coalesce(
            popular_candidates.c.popularity_raw, 0.0,
        ).label("popularity_raw")

        stmt = (
            _select_with_joins()
            .add_columns(tag_raw, author_raw, pop_raw)
            .join(
                candidate_ids,
                candidate_ids.c.product_id == products_table.c.oid,
            )
            .outerjoin(
                tag_candidates,
                tag_candidates.c.product_id == products_table.c.oid,
            )
            .outerjoin(
                author_candidates,
                author_candidates.c.product_id == products_table.c.oid,
            )
            .outerjoin(
                popular_candidates,
                popular_candidates.c.product_id == products_table.c.oid,
            )
            .where(
                products_table.c.status == ProductStatus.PUBLISHED.value,
                products_table.c.oid.not_in(
                    sa.select(excluded_products.c.oid),
                ),
            )
            # DB-side rough ordering by combined raw signal — keeps
            # the top-K candidates inside ``limit`` when there are
            # many more matches than the overfetch budget. The
            # handler re-ranks with normalization + freshness.
            .order_by(
                (tag_raw + author_raw + pop_raw).desc(),
                products_table.c.published_at.desc().nulls_last(),
            )
            .limit(limit)
        )

        rows = list((await self._session.execute(stmt)).all())
        tags_by_id = await self._tags_by_product(
            [ProductID(r.oid) for r in rows],
        )
        return [
            RecommendationCandidate(
                view=_row_to_view(
                    row, tags_by_id.get(ProductID(row.oid), []),
                ),
                tag_affinity_raw=float(row.tag_affinity_raw),
                author_affinity_raw=float(row.author_affinity_raw),
                popularity_raw=float(row.popularity_raw),
            )
            for row in rows
        ]
