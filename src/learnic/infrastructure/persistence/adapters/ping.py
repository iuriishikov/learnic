from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.ping import PingReader


class PingReaderAlchemy(PingReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def ping(self) -> None:
        await self._session.execute(text("SELECT 1"))
