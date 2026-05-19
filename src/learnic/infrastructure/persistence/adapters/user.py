from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
    UserSummaryView,
    UserView,
)
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import User, UserID
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.user import users_table


class UserMapperAlchemy(UserGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: UserID) -> User | None:
        stmt = sa.select(User).where(users_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def with_email(self, email: str) -> User | None:
        stmt = sa.select(User).where(users_table.c.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class UserReaderAlchemy(UserReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: UserID) -> UserView | None:
        avatar = files_table.alias("avatar")
        cover = files_table.alias("cover")

        stmt = (
            sa.select(
                users_table.c.oid,
                users_table.c.email,
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.patronymic,
                users_table.c.is_verified,
                users_table.c.description,
                users_table.c.website_url,
                users_table.c.portfolio_url,
                users_table.c.public_email,
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                avatar.c.size_bytes.label("avatar_size_bytes"),
                cover.c.oid.label("cover_oid"),
                cover.c.storage_name.label("cover_storage_name"),
                cover.c.bucket.label("cover_bucket"),
                cover.c.content_type.label("cover_content_type"),
                cover.c.size_bytes.label("cover_size_bytes"),
            )
            .select_from(
                users_table.outerjoin(
                    avatar,
                    sa.and_(
                        users_table.c.avatar_file_id == avatar.c.oid,
                        avatar.c.deleted_at.is_(None),
                    ),
                ).outerjoin(
                    cover,
                    sa.and_(
                        users_table.c.cover_file_id == cover.c.oid,
                        cover.c.deleted_at.is_(None),
                    ),
                )
            )
            .where(users_table.c.oid == oid)
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None

        return UserView(
            oid=UserID(row.oid),
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            patronymic=row.patronymic,
            is_verified=row.is_verified,
            description=row.description,
            website_url=row.website_url,
            portfolio_url=row.portfolio_url,
            public_email=row.public_email,
            avatar=(
                FileMeta(
                    oid=FileID(row.avatar_oid),
                    storage_name=row.avatar_storage_name,
                    bucket=row.avatar_bucket,
                    content_type=row.avatar_content_type,
                    size_bytes=row.avatar_size_bytes,
                )
                if row.avatar_oid is not None
                else None
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
        )

    @override
    async def search_by_name(
        self,
        tokens: tuple[str, ...],
        pagination: Pagination,
    ) -> list[UserSummaryView]:
        if not tokens:
            return []

        avatar = files_table.alias("avatar")

        stmt = sa.select(
            users_table.c.oid,
            users_table.c.first_name,
            users_table.c.last_name,
            users_table.c.patronymic,
            users_table.c.is_verified,
            avatar.c.oid.label("avatar_oid"),
            avatar.c.storage_name.label("avatar_storage_name"),
            avatar.c.bucket.label("avatar_bucket"),
            avatar.c.content_type.label("avatar_content_type"),
            avatar.c.size_bytes.label("avatar_size_bytes"),
        ).select_from(
            users_table.outerjoin(
                avatar,
                sa.and_(
                    users_table.c.avatar_file_id == avatar.c.oid,
                    avatar.c.deleted_at.is_(None),
                ),
            )
        )

        # Each token must match at least one of the three name fields
        # (substring, case-insensitive). Tokens combine with AND so the
        # caller can narrow with multiple words ("ivan ivanov").
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                sa.or_(
                    users_table.c.first_name.ilike(pattern),
                    users_table.c.last_name.ilike(pattern),
                    sa.and_(
                        users_table.c.patronymic.is_not(None),
                        users_table.c.patronymic.ilike(pattern),
                    ),
                )
            )

        stmt = (
            stmt.order_by(
                users_table.c.last_name.asc(),
                users_table.c.first_name.asc(),
                users_table.c.oid.asc(),
            )
            .limit(pagination.limit)
            .offset(pagination.offset)
        )

        rows = (await self._session.execute(stmt)).all()
        return [
            UserSummaryView(
                oid=UserID(row.oid),
                first_name=row.first_name,
                last_name=row.last_name,
                patronymic=row.patronymic,
                is_verified=row.is_verified,
                avatar=(
                    FileMeta(
                        oid=FileID(row.avatar_oid),
                        storage_name=row.avatar_storage_name,
                        bucket=row.avatar_bucket,
                        content_type=row.avatar_content_type,
                        size_bytes=row.avatar_size_bytes,
                    )
                    if row.avatar_oid is not None
                    else None
                ),
            )
            for row in rows
        ]
