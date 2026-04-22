from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.file import FileView
from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
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
                avatar.c.oid.label("avatar_oid"),
                avatar.c.storage_name.label("avatar_storage_name"),
                avatar.c.bucket.label("avatar_bucket"),
                avatar.c.content_type.label("avatar_content_type"),
                cover.c.oid.label("cover_oid"),
                cover.c.storage_name.label("cover_storage_name"),
                cover.c.bucket.label("cover_bucket"),
                cover.c.content_type.label("cover_content_type"),
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
            avatar=(
                FileView(
                    oid=FileID(row.avatar_oid),
                    storage_name=row.avatar_storage_name,
                    bucket=row.avatar_bucket,
                    content_type=row.avatar_content_type,
                )
                if row.avatar_oid is not None
                else None
            ),
            cover=(
                FileView(
                    oid=FileID(row.cover_oid),
                    storage_name=row.cover_storage_name,
                    bucket=row.cover_bucket,
                    content_type=row.cover_content_type,
                )
                if row.cover_oid is not None
                else None
            ),
        )
