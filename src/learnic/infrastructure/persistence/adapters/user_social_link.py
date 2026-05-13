from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.user_social_link import (
    UserSocialLinkGateway,
    UserSocialLinkReader,
    UserSocialLinkView,
)
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.models import UserID
from learnic.entities.user_social_link.models import UserSocialLink
from learnic.infrastructure.persistence.models.user_social_link import (
    user_social_links_table,
)


class UserSocialLinkMapperAlchemy(UserSocialLinkGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserSocialLink]:
        stmt = (
            sa.select(UserSocialLink)
            .where(user_social_links_table.c.user_id == user_id)
            .order_by(user_social_links_table.c.position.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete_for_user(self, user_id: UserID) -> None:
        stmt = sa.delete(user_social_links_table).where(
            user_social_links_table.c.user_id == user_id,
        )
        await self._session.execute(stmt)


class UserSocialLinkReaderAlchemy(UserSocialLinkReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserSocialLinkView]:
        stmt = (
            sa.select(
                user_social_links_table.c.kind,
                user_social_links_table.c.url,
                user_social_links_table.c.position,
            )
            .where(user_social_links_table.c.user_id == user_id)
            .order_by(user_social_links_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            UserSocialLinkView(
                kind=SocialLinkKind(row.kind),
                url=row.url,
                position=row.position,
            )
            for row in rows
        ]
