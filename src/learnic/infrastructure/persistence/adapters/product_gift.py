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
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.adapters._embedded_user import (
    embedded_user_columns,
    user_view_from_row,
    user_view_from_row_optional,
)
from learnic.infrastructure.persistence.models.file import files_table
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
_recipient_avatar = files_table.alias("recipient_avatar")
_recipient_cover = files_table.alias("recipient_cover")
_gifter_avatar = files_table.alias("gifter_avatar")
_gifter_cover = files_table.alias("gifter_cover")


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
            *embedded_user_columns(
                _recipient_users,
                _recipient_avatar,
                _recipient_cover,
                "recipient",
            ),
            *embedded_user_columns(
                _gifter_users, _gifter_avatar, _gifter_cover, "gifter",
            ),
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
                _gifter_avatar,
                sa.and_(
                    _gifter_users.c.avatar_file_id == _gifter_avatar.c.oid,
                    _gifter_avatar.c.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                _gifter_cover,
                sa.and_(
                    _gifter_users.c.cover_file_id == _gifter_cover.c.oid,
                    _gifter_cover.c.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                _recipient_users,
                product_gifts_table.c.recipient_id == _recipient_users.c.oid,
            )
            .outerjoin(
                _recipient_avatar,
                sa.and_(
                    _recipient_users.c.avatar_file_id
                    == _recipient_avatar.c.oid,
                    _recipient_avatar.c.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                _recipient_cover,
                sa.and_(
                    _recipient_users.c.cover_file_id
                    == _recipient_cover.c.oid,
                    _recipient_cover.c.deleted_at.is_(None),
                ),
            ),
        )

    def _row_to_view(self, row: sa.Row[Any]) -> ProductGiftView:
        return ProductGiftView(
            oid=ProductGiftID(row.oid),
            product_id=ProductID(row.product_id),
            product_name=row.product_name,
            recipient=user_view_from_row_optional(row, "recipient"),
            invited_email=row.invited_email,
            status=row.status,
            gifter=user_view_from_row(row, "gifter"),
            invite_expires_at=row.invite_expires_at,
            created_at=row.created_at,
            accepted_at=row.accepted_at,
            declined_at=row.declined_at,
            revoked_at=row.revoked_at,
        )
