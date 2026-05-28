from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
    ProductGiftReader,
    ProductGiftView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.product_gift import (
    product_gifts_table,
)
from learnic.infrastructure.persistence.models.user import users_table


class ProductGiftMapperAlchemy(ProductGiftGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: ProductGiftID,
    ) -> ProductGift | None:
        stmt = sa.select(ProductGift).where(
            product_gifts_table.c.oid == oid,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def active_for_product_and_user(
        self,
        product_id: ProductID,
        recipient_id: UserID,
    ) -> ProductGift | None:
        stmt = sa.select(ProductGift).where(
            product_gifts_table.c.product_id == product_id,
            product_gifts_table.c.recipient_id == recipient_id,
            product_gifts_table.c.status.in_(
                [
                    GiftStatus.PENDING_INVITE.value,
                    GiftStatus.ACCEPTED.value,
                ],
            ),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def pending_for_product_and_email(
        self,
        product_id: ProductID,
        invited_email: str,
    ) -> ProductGift | None:
        stmt = sa.select(ProductGift).where(
            product_gifts_table.c.product_id == product_id,
            product_gifts_table.c.invited_email == invited_email,
            product_gifts_table.c.status
            == GiftStatus.PENDING_INVITE.value,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def count_email_invites_by_actor_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(product_gifts_table)
            .where(
                product_gifts_table.c.invited_by == actor_id,
                product_gifts_table.c.invited_email.is_not(None),
                product_gifts_table.c.created_at >= since,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @override
    async def delete_expired_pending_invites(
        self,
        expires_before: datetime,
    ) -> int:
        # ``invite_expires_at`` is non-null for every PENDING_INVITE
        # row by construction; the explicit ``is_not(None)`` keeps the
        # predicate well-defined and lets Postgres use the partial
        # index without pulling NULL rows.
        stmt = sa.delete(product_gifts_table).where(
            product_gifts_table.c.status == GiftStatus.PENDING_INVITE.value,
            product_gifts_table.c.invite_expires_at.is_not(None),
            product_gifts_table.c.invite_expires_at < expires_before,
        )
        result = await self._session.execute(stmt)
        rowcount: int | None = getattr(result, "rowcount", None)
        return rowcount or 0


_recipient_users = aliased(users_table, name="recipient")
_gifter_users = aliased(users_table, name="gifter")


def _row_to_recipient(row: sa.Row[Any]) -> UserRefView | None:
    if row.recipient_oid is None:
        return None
    return UserRefView(
        oid=UserID(row.recipient_oid),
        email=row.recipient_email,
        first_name=row.recipient_first_name,
        last_name=row.recipient_last_name,
        patronymic=row.recipient_patronymic,
    )


def _row_to_gifter(row: sa.Row[Any]) -> UserRefView:
    return UserRefView(
        oid=UserID(row.gifter_oid),
        email=row.gifter_email,
        first_name=row.gifter_first_name,
        last_name=row.gifter_last_name,
        patronymic=row.gifter_patronymic,
    )


class ProductGiftReaderAlchemy(ProductGiftReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: ProductGiftID,
    ) -> ProductGiftView | None:
        stmt = self._select_with_refs().where(
            product_gifts_table.c.oid == oid,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return self._row_to_view(row)

    @override
    async def for_product(
        self,
        product_id: ProductID,
        pagination: Pagination,
    ) -> list[ProductGiftView]:
        stmt = (
            self._select_with_refs()
            .where(product_gifts_table.c.product_id == product_id)
            .order_by(product_gifts_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [self._row_to_view(row) for row in rows]

    @override
    async def for_user(
        self,
        recipient_id: UserID,
        pagination: Pagination,
    ) -> list[ProductGiftView]:
        stmt = (
            self._select_with_refs()
            .where(product_gifts_table.c.recipient_id == recipient_id)
            .order_by(product_gifts_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [self._row_to_view(row) for row in rows]

    def _select_with_refs(self) -> sa.Select[Any]:
        return sa.select(
            product_gifts_table.c.oid,
            product_gifts_table.c.product_id,
            product_gifts_table.c.invited_email,
            product_gifts_table.c.status,
            product_gifts_table.c.invite_expires_at,
            product_gifts_table.c.created_at,
            product_gifts_table.c.accepted_at,
            product_gifts_table.c.declined_at,
            product_gifts_table.c.revoked_at,
            products_table.c.name.label("product_name"),
            _recipient_users.c.oid.label("recipient_oid"),
            _recipient_users.c.email.label("recipient_email"),
            _recipient_users.c.first_name.label("recipient_first_name"),
            _recipient_users.c.last_name.label("recipient_last_name"),
            _recipient_users.c.patronymic.label("recipient_patronymic"),
            _gifter_users.c.oid.label("gifter_oid"),
            _gifter_users.c.email.label("gifter_email"),
            _gifter_users.c.first_name.label("gifter_first_name"),
            _gifter_users.c.last_name.label("gifter_last_name"),
            _gifter_users.c.patronymic.label("gifter_patronymic"),
        ).select_from(
            product_gifts_table.join(
                products_table,
                product_gifts_table.c.product_id == products_table.c.oid,
            )
            .join(
                _gifter_users,
                product_gifts_table.c.invited_by == _gifter_users.c.oid,
            )
            .outerjoin(
                _recipient_users,
                product_gifts_table.c.recipient_id == _recipient_users.c.oid,
            ),
        )

    def _row_to_view(self, row: sa.Row[Any]) -> ProductGiftView:
        return ProductGiftView(
            oid=ProductGiftID(row.oid),
            product_id=ProductID(row.product_id),
            product_name=row.product_name,
            recipient=_row_to_recipient(row),
            invited_email=row.invited_email,
            status=row.status,
            gifter=_row_to_gifter(row),
            invite_expires_at=row.invite_expires_at,
            created_at=row.created_at,
            accepted_at=row.accepted_at,
            declined_at=row.declined_at,
            revoked_at=row.revoked_at,
        )
