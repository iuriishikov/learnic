from typing import Any, Final

import sqlalchemy as sa
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
        stmt = sa.select(tags_table)
        if normalized:
            # Substring match on slug — the slug is already lower-cased
            # and whitespace-collapsed at insert, so a plain LIKE
            # works without ILIKE/COLLATE gymnastics.
            stmt = stmt.where(
                tags_table.c.slug.like(f"%{normalized}%"),
            )
        stmt = (
            stmt.order_by(tags_table.c.name.asc())
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
