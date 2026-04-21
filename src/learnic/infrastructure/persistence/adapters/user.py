from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.user import (
    UserGateway,
    UserReader,
    UserView,
)
from learnic.entities.user.models import User, UserID
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
        stmt = sa.select(
            users_table.c.oid,
            users_table.c.email,
            users_table.c.first_name,
            users_table.c.last_name,
            users_table.c.patronymic,
        ).where(users_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return UserView(
            oid=UserID(row.oid),
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            patronymic=row.patronymic,
        )
