from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.tag import (
    ProductTagsSaver,
    TagGateway,
    TagReader,
    TagView,
)
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.tag.ids import TagID
from learnic.entities.tag.models import Tag
from learnic.entities.tag.value_objects import TagSlug
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.tag import (
    product_tags_table,
    tags_table,
)


def _row_to_view(row: sa.Row[Any]) -> TagView:
    return TagView(
        oid=TagID(row.oid),
        name=row.name,
        color=row.color,
    )


class TagMapperAlchemy(TagGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: TagID) -> Tag | None:
        stmt = sa.select(Tag).where(tags_table.c.oid == oid)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def with_ids(self, oids: list[TagID]) -> list[Tag]:
        if not oids:
            return []
        stmt = sa.select(Tag).where(tags_table.c.oid.in_(oids))
        return list((await self._session.execute(stmt)).scalars().all())

    @override
    async def with_slug(self, slug: TagSlug) -> Tag | None:
        stmt = sa.select(Tag).where(tags_table.c.slug == slug.value)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def get_or_create_by_slug(self, tag: Tag) -> Tag:
        # Atomic get-or-create: ``INSERT ... ON CONFLICT (slug) DO
        # NOTHING`` serialises on the (possibly uncommitted) conflicting
        # row, so two concurrent first-uses of the same slug no longer
        # race into a ``uq_tags_slug`` IntegrityError → 500. The
        # follow-up SELECT returns whichever row won (the existing tag or
        # the one we just inserted), so the result is never ``None``.
        stmt = pg_insert(tags_table).values(
            oid=tag.oid,
            name=tag.name.value,
            slug=tag.slug.value,
            color=tag.color.value,
            created_by=tag.created_by,
            created_at=tag.created_at,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[tags_table.c.slug],
        )
        await self._session.execute(stmt)
        persisted = await self.with_slug(tag.slug)
        return persisted if persisted is not None else tag


class TagReaderAlchemy(TagReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def search(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[TagView]:
        normalized = " ".join(query.split()).lower()
        # Empty query → the full tag pool, name-ordered (the SPA's
        # "browse all" state; the popularity row comes from ``popular``).
        if not normalized:
            stmt = (
                sa.select(
                    tags_table.c.oid,
                    tags_table.c.name,
                    tags_table.c.color,
                )
                .order_by(tags_table.c.name.asc())
                .limit(pagination.limit)
                .offset(pagination.offset)
            )
            rows = (await self._session.execute(stmt)).all()
            return [_row_to_view(row) for row in rows]

        # Full-text + trigram fuzzy over the tag ``name`` — the same
        # engine as user/product search. ``search_text`` is stored
        # lower-cased, so the query is lowered too (trigram ops are
        # case-sensitive; tsvector matching is dictionary-driven).
        await self._session.execute(
            sa.text("SET LOCAL pg_trgm.word_similarity_threshold = 0.4"),
        )
        russian_regconfig: sa.ColumnElement[str] = sa.literal_column(
            "'russian'::regconfig",
        )
        tsq = sa.func.websearch_to_tsquery(russian_regconfig, normalized)
        rank_ts = sa.func.ts_rank_cd(
            tags_table.c.search_vector, tsq,
        ).label("rank_ts")
        rank_trgm = sa.func.word_similarity(
            normalized, tags_table.c.search_text,
        ).label("rank_trgm")
        stmt = (
            sa.select(
                tags_table.c.oid,
                tags_table.c.name,
                tags_table.c.color,
                rank_ts,
                rank_trgm,
            )
            .where(
                sa.or_(
                    tags_table.c.search_vector.op("@@")(tsq),
                    tags_table.c.search_text.op("%>")(normalized),
                )
            )
            # tsvector (morphology) twice the weight of trigram (typos);
            # tie-break by name then ``oid`` for stable pagination.
            .order_by(
                (rank_ts * sa.literal(2.0) + rank_trgm).desc(),
                tags_table.c.name.asc(),
                tags_table.c.oid.asc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def for_product(self, product_id: ProductID) -> list[TagView]:
        stmt = (
            sa.select(tags_table, product_tags_table.c.position)
            .select_from(
                product_tags_table.join(
                    tags_table,
                    tags_table.c.oid == product_tags_table.c.tag_id,
                ),
            )
            .where(product_tags_table.c.product_id == product_id)
            .order_by(product_tags_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def popular(self, limit: int) -> list[TagView]:
        # Count usages only across PUBLISHED products — draft /
        # archived slices are not part of what a marketplace
        # visitor can see, so a tag whose only carriers are drafts
        # should not surface in the public popular row.
        usage_count = sa.func.count(product_tags_table.c.product_id).label(
            "usage_count",
        )
        stmt = (
            sa.select(
                tags_table.c.oid,
                tags_table.c.name,
                tags_table.c.color,
                usage_count,
            )
            .select_from(
                tags_table.join(
                    product_tags_table,
                    product_tags_table.c.tag_id == tags_table.c.oid,
                ).join(
                    products_table,
                    sa.and_(
                        products_table.c.oid
                        == product_tags_table.c.product_id,
                        products_table.c.status
                        == ProductStatus.PUBLISHED.value,
                    ),
                ),
            )
            .group_by(
                tags_table.c.oid,
                tags_table.c.name,
                tags_table.c.color,
            )
            # `usage_count` first so the SPA's chip row is sorted by
            # raw popularity; `name` is the deterministic tiebreaker
            # so two equally-popular tags keep a stable order across
            # page refreshes.
            .order_by(
                usage_count.desc(),
                tags_table.c.name.asc(),
            )
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]


class ProductTagsSaverAlchemy(ProductTagsSaver):
    """Rewrite the ``product_tags`` slice for one product in a single round-trip.

    DELETE everything for ``product_id``, then bulk-INSERT the new
    positions. Both statements run on the caller's transaction and
    do not commit on their own — the command handler owns the
    commit decision.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def replace(
        self,
        product_id: ProductID,
        tag_ids: list[TagID],
    ) -> None:
        # Flush pending ORM state first so newly-created ``Tag``
        # entities (``session.add(...)``-ed earlier in the
        # transaction) materialise as rows in ``tags`` before the
        # bulk INSERT below references them via FK. ``session.execute``
        # over Core constructs (``sa.delete`` / ``sa.insert``) does
        # NOT trigger autoflush — only ORM-level queries do — so the
        # explicit flush is load-bearing.
        await self._session.flush()
        await self._session.execute(
            sa.delete(product_tags_table).where(
                product_tags_table.c.product_id == product_id,
            ),
        )
        if not tag_ids:
            return
        await self._session.execute(
            sa.insert(product_tags_table),
            [
                {
                    "product_id": product_id,
                    "tag_id": tag_id,
                    "position": position,
                }
                for position, tag_id in enumerate(tag_ids)
            ],
        )
