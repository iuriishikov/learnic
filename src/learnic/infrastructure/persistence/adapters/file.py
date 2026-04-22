from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.file import (
    FilesGateway,
    FilesReader,
    FileView,
)
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.infrastructure.persistence.models.file import files_table


class FilesMapperAlchemy(FilesGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: FileID) -> File | None:
        stmt = sa.select(File).where(files_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class FilesReaderAlchemy(FilesReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: FileID) -> FileView | None:
        stmt = sa.select(
            files_table.c.oid,
            files_table.c.storage_name,
            files_table.c.bucket,
            files_table.c.content_type,
        ).where(
            files_table.c.oid == oid,
            files_table.c.deleted_at.is_(None),
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return FileView(
            oid=FileID(row.oid),
            storage_name=row.storage_name,
            bucket=row.bucket,
            content_type=row.content_type,
        )
