from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.file import FileView
from learnic.application.common.persistence.user_experience import (
    UserExperienceGateway,
    UserExperienceReader,
    UserExperienceView,
)
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.entities.user_experience.models import UserExperience
from learnic.infrastructure.persistence.models.file import files_table
from learnic.infrastructure.persistence.models.user_experience import (
    user_experiences_table,
)


class UserExperienceMapperAlchemy(UserExperienceGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: UserExperienceID,
    ) -> UserExperience | None:
        stmt = sa.select(UserExperience).where(
            user_experiences_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserExperience]:
        stmt = (
            sa.select(UserExperience)
            .where(user_experiences_table.c.user_id == user_id)
            .order_by(
                user_experiences_table.c.start_date.desc(),
                user_experiences_table.c.oid.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, experience: UserExperience) -> None:
        await self._session.delete(experience)


class UserExperienceReaderAlchemy(UserExperienceReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserExperienceView]:
        icon = files_table.alias("icon")
        stmt = (
            sa.select(
                user_experiences_table.c.oid,
                user_experiences_table.c.user_id,
                user_experiences_table.c.title,
                user_experiences_table.c.description,
                user_experiences_table.c.start_date,
                user_experiences_table.c.end_date,
                user_experiences_table.c.source_url,
                icon.c.oid.label("icon_oid"),
                icon.c.storage_name.label("icon_storage_name"),
                icon.c.bucket.label("icon_bucket"),
                icon.c.content_type.label("icon_content_type"),
            )
            .select_from(
                user_experiences_table.outerjoin(
                    icon,
                    sa.and_(
                        user_experiences_table.c.icon_file_id == icon.c.oid,
                        icon.c.deleted_at.is_(None),
                    ),
                ),
            )
            .where(user_experiences_table.c.user_id == user_id)
            .order_by(
                user_experiences_table.c.start_date.desc(),
                user_experiences_table.c.oid.asc(),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            UserExperienceView(
                oid=UserExperienceID(row.oid),
                user_id=UserID(row.user_id),
                title=row.title,
                description=row.description,
                start_date=row.start_date,
                end_date=row.end_date,
                source_url=row.source_url,
                icon=(
                    FileView(
                        oid=FileID(row.icon_oid),
                        storage_name=row.icon_storage_name,
                        bucket=row.icon_bucket,
                        content_type=row.icon_content_type,
                    )
                    if row.icon_oid is not None
                    else None
                ),
            )
            for row in rows
        ]
