from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import (
    ProductGateway,
    ProductReader,
    ProductView,
    WebinarDetailsView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.webinar_details import WebinarDetails
from learnic.entities.product_collaboration.enums import (
    CollaborationStatus,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.product import (
    product_webinar_details_table,
    products_table,
)
from learnic.infrastructure.persistence.models.product_collaboration import (
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.user import users_table


class ProductMapperAlchemy(ProductGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: ProductID) -> Product | None:
        stmt = sa.select(Product).where(products_table.c.oid == oid)
        result = await self._session.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            return None
        if product.type is ProductType.WEBINAR:
            details_stmt = sa.select(WebinarDetails).where(
                product_webinar_details_table.c.product_id == oid,
            )
            details_result = await self._session.execute(details_stmt)
            product.webinar_details = details_result.scalar_one_or_none()
        return product

    @override
    async def delete(self, product: Product) -> None:
        await self._session.delete(product)


def _row_to_view(row: sa.Row[Any]) -> ProductView:
    webinar_details: WebinarDetailsView | None = None
    if row.wd_total_lessons is not None:
        webinar_details = WebinarDetailsView(
            total_lessons=row.wd_total_lessons,
            default_duration_minutes=row.wd_default_duration_minutes,
            allow_recording=row.wd_allow_recording,
            default_max_participants=row.wd_default_max_participants,
            default_stream_url=row.wd_default_stream_url,
            access_window_minutes=row.wd_access_window_minutes,
        )

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
        webinar_details=webinar_details,
        cover_file_id=(
            FileID(row.cover_file_id) if row.cover_file_id is not None else None
        ),
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _select_with_joins() -> sa.Select[Any]:
    wd = product_webinar_details_table
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
        products_table.c.cover_file_id,
        users_table.c.oid.label("author_oid"),
        users_table.c.email.label("author_email"),
        users_table.c.first_name.label("author_first_name"),
        users_table.c.last_name.label("author_last_name"),
        users_table.c.patronymic.label("author_patronymic"),
        wd.c.total_lessons.label("wd_total_lessons"),
        wd.c.default_duration_minutes.label("wd_default_duration_minutes"),
        wd.c.allow_recording.label("wd_allow_recording"),
        wd.c.default_max_participants.label("wd_default_max_participants"),
        wd.c.default_stream_url.label("wd_default_stream_url"),
        wd.c.access_window_minutes.label("wd_access_window_minutes"),
    ).select_from(
        products_table.join(
            users_table,
            products_table.c.author_id == users_table.c.oid,
        ).outerjoin(
            wd,
            products_table.c.oid == wd.c.product_id,
        ),
    )


class ProductReaderAlchemy(ProductReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: ProductID) -> ProductView | None:
        stmt = _select_with_joins().where(products_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _row_to_view(row)

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
            product_collaborations_table.c.status
            == CollaborationStatus.ACTIVE.value,
        )
        stmt = (
            _select_with_joins()
            .where(
                sa.or_(
                    products_table.c.author_id == user_id,
                    products_table.c.oid.in_(active_collab_product_ids),
                ),
            )
            .order_by(products_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def published(
        self,
        pagination: Pagination,
    ) -> list[ProductView]:
        stmt = (
            _select_with_joins()
            .where(products_table.c.status == ProductStatus.PUBLISHED.value)
            .order_by(products_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

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
