from typing import Protocol


class PingReader(Protocol):
    async def ping(self) -> None: ...
